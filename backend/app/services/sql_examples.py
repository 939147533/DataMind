"""few-shot 示例池：按数据源缓存历史成功 SQL，并按与当前问题的相关性排序。

Agent 每轮对话都会挑选历史成功 SQL 注入提示词。原实现每轮都扫库、按“最近 N 条”截取，
既重复查询又与当前问题无关。这里集中两件事：

1. 缓存：按 datasource 缓存“已解析好的候选示例”（表名/词元只算一次），
   ``sql_service`` 写入 query_history 后调用 ``record()`` 增量合并（无需重扫），
   解析规则升级时可用 ``invalidate()`` 全量重建，另有 TTL 兜底。
2. 排序：按提问相似度 + 表名重合度 + 使用频次加权打分，挑出对当前问题最有参考价值的示例。

注：中文提问若未点名英文表名，相似度通常为 0，此时排序主要由表名与频次决定。
"""
import re
import time
from dataclasses import dataclass, replace

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ..models import QueryHistory

CANDIDATE_POOL_SIZE = 120
MAX_SQL_LENGTH = 400
CACHE_TTL_SECONDS = 300
EXAMPLE_LIMIT = 3

# 排序权重：表名命中比泛化词元命中更有信号，频次仅作微调
WEIGHT_SIMILARITY = 1.0
WEIGHT_TABLE = 1.5
WEIGHT_FREQUENCY = 0.6

PROMPT_HEADER = "历史成功执行的 SQL 示例（仅供风格参考）："

SQL_KEYWORDS = frozenset(
    """select from where and or not in as join left right inner outer full cross on group by order having
    limit offset union all distinct insert into values update set delete create alter drop truncate table view
    index with case when then else end asc desc between like is null exists count sum avg min max""".split()
)

_ASCII_RE = re.compile(r"[A-Za-z_][A-Za-z0-9_]*")
_CJK_RUN_RE = re.compile(r"[\u4e00-\u9fff]+")
_TABLE_RE = re.compile(r"\b(?:from|join)\s+[`\[\"]?(?:[A-Za-z_]\w*\.)?[`\[\"]?([A-Za-z_]\w*)", re.I)
_WS_RE = re.compile(r"\s+")


@dataclass(frozen=True)
class SqlExample:
    sql: str
    key: str
    tables: frozenset
    tokens: frozenset
    frequency: int
    recency: int


_cache: dict[int, tuple[float, tuple[SqlExample, ...]]] = {}


def invalidate(ds_id: int | None = None) -> None:
    """全量失效示例缓存（解析规则变更、测试或需要强制重建时使用）。"""
    if ds_id is None:
        _cache.clear()
    else:
        _cache.pop(ds_id, None)


def record(ds_id: int | None, sql: str) -> None:
    """把一条新写入的成功 SQL 增量合并进缓存池。

    未缓存时直接返回（下次查询会从库里重建），因此不会因频繁写入而反复清空缓存；
    重复执行的 SQL 只累加频次并提升新鲜度，不需要重新扫库或重新解析。
    """
    if not ds_id:
        return
    text = (sql or "").strip()
    if not text or len(text) > MAX_SQL_LENGTH:
        return
    cached = _cache.get(ds_id)
    if cached is None:
        return
    key = _normalize(text)
    if not key:
        return
    loaded_at, examples = cached
    merged: list[SqlExample] = []
    matched = False
    for example in examples:
        if example.key == key:
            matched = True
            merged.append(replace(example, recency=0, frequency=example.frequency + 1))
        else:
            merged.append(replace(example, recency=example.recency + 1))
    if not matched:
        merged.insert(0, _make_example(text, key, recency=0, frequency=1))
    _cache[ds_id] = (loaded_at, tuple(merged[:CANDIDATE_POOL_SIZE]))


def _cjk_bigrams(text: str) -> set:
    tokens: set[str] = set()
    for run in _CJK_RUN_RE.findall(text or ""):
        if len(run) == 1:
            tokens.add(run)
        else:
            tokens.update(run[i : i + 2] for i in range(len(run) - 1))
    return tokens


def _tokenize(text: str, strip_keywords: bool = False) -> frozenset:
    """切分词元：ASCII 标识符（含下划线拆词）+ 中文二元组。

    中文按二元组切分，是为了让 "查询用户表" 能命中 SQL 里的中文字面量；
    英文标识符保留原样并额外拆出下划线片段，便于 "order_amount" 与 "amount" 互相命中。
    """
    tokens = {t.lower() for t in _ASCII_RE.findall(text or "")}
    if strip_keywords:
        tokens -= SQL_KEYWORDS
    for token in list(tokens):
        if "_" in token:
            tokens.update(part for part in token.split("_") if part)
    tokens.update(_cjk_bigrams(text or ""))
    return frozenset(tokens)


def _extract_tables(sql: str) -> frozenset:
    """提取 SQL 涉及的表名；解析失败时退化为 FROM/JOIN 正则。"""
    try:
        from sqlglot import exp, parse

        tables = set()
        for statement in parse(sql):
            if statement is None:
                continue
            tables.update((node.name or "").lower() for node in statement.find_all(exp.Table))
        tables.discard("")
        if tables:
            return frozenset(tables)
    except Exception:  # noqa: BLE001
        pass
    return frozenset(m.group(1).lower() for m in _TABLE_RE.finditer(sql))


def _normalize(sql: str) -> str:
    return _WS_RE.sub(" ", sql).strip().rstrip(";").strip().lower()


def _make_example(sql: str, key: str, recency: int, frequency: int) -> SqlExample:
    """只在这里解析表名与词元，保证解析成本按“去重后的 SQL 条数”摊销。"""
    return SqlExample(
        sql=sql,
        key=key,
        tables=_extract_tables(sql),
        tokens=_tokenize(sql, strip_keywords=True),
        frequency=frequency,
        recency=recency,
    )


def _build_candidates(rows: list) -> tuple[SqlExample, ...]:
    """按归一化 SQL 归并历史记录，重复执行只保留最新文本并累加频次。"""
    grouped: dict[str, dict] = {}
    for index, row in enumerate(rows):
        sql = (row.sql_text or "").strip()
        if not sql or len(sql) > MAX_SQL_LENGTH:
            continue
        key = _normalize(sql)
        if not key:
            continue
        if key in grouped:
            grouped[key]["frequency"] += 1
            continue
        grouped[key] = {"sql": sql, "recency": index, "frequency": 1}
    return tuple(
        _make_example(item["sql"], key, item["recency"], item["frequency"]) for key, item in grouped.items()
    )


async def get_candidates(db: AsyncSession, ds_id: int | None) -> tuple[SqlExample, ...]:
    """取某数据源的候选示例；命中缓存则不再查询数据库。"""
    if not ds_id:
        return ()
    cached = _cache.get(ds_id)
    if cached is not None and time.monotonic() - cached[0] < CACHE_TTL_SECONDS:
        return cached[1]
    rows = (
        await db.execute(
            select(QueryHistory)
            .where(QueryHistory.datasource_id == ds_id, QueryHistory.status == "success")
            .order_by(QueryHistory.id.desc())
            .limit(CANDIDATE_POOL_SIZE)
        )
    ).scalars().all()
    examples = _build_candidates(list(rows))
    _cache[ds_id] = (time.monotonic(), examples)
    return examples


def _score(example: SqlExample, question_tokens: frozenset, question_tables: set, max_frequency: int) -> float:
    similarity = len(question_tokens & example.tokens) / len(question_tokens) if question_tokens else 0.0
    if question_tables and example.tables:
        table_hit = len(question_tables & example.tables) / len(example.tables)
    else:
        table_hit = 0.0
    frequency = example.frequency / max_frequency if max_frequency else 0.0
    return WEIGHT_SIMILARITY * similarity + WEIGHT_TABLE * table_hit + WEIGHT_FREQUENCY * frequency


def rank_examples(examples: tuple[SqlExample, ...], question: str, limit: int = EXAMPLE_LIMIT) -> list[SqlExample]:
    """按与提问的相关性排序；同分时较新的示例优先。"""
    if not examples or limit <= 0:
        return []
    question_tokens = _tokenize(question)
    universe = set().union(*(example.tables for example in examples))
    lowered = (question or "").lower()
    question_tables = {table for table in universe if len(table) >= 3 and table in lowered}
    max_frequency = max(example.frequency for example in examples)
    ranked = sorted(
        examples,
        key=lambda example: (-_score(example, question_tokens, question_tables, max_frequency), example.recency),
    )
    return ranked[:limit]


def format_prompt(examples: list[SqlExample]) -> str:
    if not examples:
        return ""
    return PROMPT_HEADER + "\n" + "\n".join(example.sql for example in examples)


async def build_few_shot_block(db: AsyncSession, ds_id: int | None, question: str = "", limit: int = EXAMPLE_LIMIT) -> str:
    """组装注入 system prompt 的 few-shot 文本块；无可用示例时返回空串。"""
    examples = await get_candidates(db, ds_id)
    return format_prompt(rank_examples(examples, question, limit))
