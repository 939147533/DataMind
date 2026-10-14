"""SQL 执行服务：拆分、分类、授权、执行、确认、历史、审计。"""
import asyncio
import json
import re
import time
import uuid
from datetime import datetime, timedelta

from fastapi import HTTPException
from prometheus_client import Counter as PromCounter
from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlglot import transpile

from ..adapters import AdapterError, get_adapter
from ..adapters.base import ConnectionInfo
from ..config import EXECUTION_CONFIRM_TIMEOUT, MAX_ROWS_PER_PAGE
from ..models import DataSource, PendingExecution, QueryHistory
from ..permissions import check_sql_permission
from ..security import decrypt_text
from . import sql_examples
from .audit_service import record_audit
from .ssh_tunnel import existing_local_port, get_local_port

READ_KEYWORDS = {"SELECT", "WITH", "SHOW", "DESC", "DESCRIBE", "EXPLAIN", "PRAGMA", "VALUES"}
SESSION_KEYWORDS = {"SET", "USE", "BEGIN", "COMMIT", "START"}
DML_KEYWORDS = {"INSERT", "UPDATE", "DELETE", "MERGE", "REPLACE", "UPSERT", "CALL"}
DDL_KEYWORDS = {"CREATE", "ALTER", "DROP", "TRUNCATE", "RENAME", "GRANT", "REVOKE"}
VERB_KEYWORDS = READ_KEYWORDS | SESSION_KEYWORDS | DML_KEYWORDS | DDL_KEYWORDS

# 首个关键字是只读、但语句本身会写数据/写文件/加锁的写法；命中后提升风险等级
READ_ESCALATIONS = (
    (re.compile(r"\binto\b", re.I), "DDL"),
    (re.compile(r"\bfor\s+(?:update|share)\b", re.I), "DML"),
    (re.compile(r"\block\s+in\s+share\s+mode\b", re.I), "DML"),
)
READ_ESCALATION_KEYWORDS = {"SELECT", "WITH", "VALUES"}

_WORD_RE = re.compile(r"[A-Za-z_][A-Za-z0-9_$]*")
_EXPLAIN_RE = re.compile(r"^\s*explain\s*(?:\(([^)]*)\))?\s*", re.I)
_EXPLAIN_ANALYZE_RE = re.compile(r"analyze\b", re.I)

SQL_EXECUTIONS = PromCounter("sql_executions_total", "SQL 执行总数", ["operation_type", "status"])


def split_statements(sql: str) -> list[str]:
    """按分号拆分 SQL（正确处理引号与注释）。"""
    statements: list[str] = []
    current: list[str] = []
    in_single = in_double = in_backtick = False
    in_line_comment = in_block_comment = False
    i, n = 0, len(sql)
    while i < n:
        ch = sql[i]
        nxt = sql[i + 1] if i + 1 < n else ""
        if in_line_comment:
            current.append(ch)
            if ch == "\n":
                in_line_comment = False
            i += 1
            continue
        if in_block_comment:
            current.append(ch)
            if ch == "*" and nxt == "/":
                current.append(nxt)
                i += 2
                in_block_comment = False
                continue
            i += 1
            continue
        if in_single:
            current.append(ch)
            if ch == "'":
                if nxt == "'":
                    current.append(nxt)
                    i += 2
                    continue
                in_single = False
            i += 1
            continue
        if in_double:
            current.append(ch)
            if ch == '"':
                in_double = False
            i += 1
            continue
        if in_backtick:
            current.append(ch)
            if ch == "`":
                in_backtick = False
            i += 1
            continue
        if ch == "-" and nxt == "-" or ch == "#":
            in_line_comment = True
            current.append(ch)
            i += 1
            continue
        if ch == "/" and nxt == "*":
            in_block_comment = True
            current.append(ch)
            i += 1
            continue
        if ch in ("'", '"', "`"):
            if ch == "'":
                in_single = True
            elif ch == '"':
                in_double = True
            else:
                in_backtick = True
            current.append(ch)
            i += 1
            continue
        if ch == ";":
            stmt = "".join(current).strip()
            if stmt:
                statements.append(stmt)
            current = []
            i += 1
            continue
        current.append(ch)
        i += 1
    tail = "".join(current).strip()
    if tail:
        statements.append(tail)
    return statements


def _first_keyword(sql: str) -> str:
    text = sql.lstrip()
    for _ in range(8):
        if text.startswith("--"):
            idx = text.find("\n")
            text = text[idx + 1 :].lstrip() if idx >= 0 else ""
        elif text.startswith("/*"):
            idx = text.find("*/")
            text = text[idx + 2 :].lstrip() if idx >= 0 else ""
        elif text.startswith("("):
            text = text[1:].lstrip()
        else:
            break
    match = text.split(None, 1)
    return match[0].upper() if match else ""


def _mask_literals(sql: str) -> str:
    """把字符串字面量与注释替换为空格，避免其中的关键字参与语句分类。"""
    chars = list(sql)
    quote = ""
    in_line = in_block = False
    i, n = 0, len(sql)
    while i < n:
        ch = sql[i]
        nxt = sql[i + 1] if i + 1 < n else ""
        if in_line:
            if ch == "\n":
                in_line = False
            else:
                chars[i] = " "
        elif in_block:
            if ch == "*" and nxt == "/":
                chars[i] = chars[i + 1] = " "
                in_block = False
                i += 1
            elif ch != "\n":
                chars[i] = " "
        elif quote:
            if ch == "\\" and quote != "`" and nxt:
                chars[i] = chars[i + 1] = " "
                i += 1
            elif ch == quote:
                chars[i] = " "
                if nxt == quote:  # 连续两个引号是转义
                    chars[i + 1] = " "
                    i += 1
                else:
                    quote = ""
            elif ch != "\n":
                chars[i] = " "
        elif ch in "'\"`":
            quote = ch
            chars[i] = " "
        elif ch == "-" and nxt == "-":
            chars[i] = chars[i + 1] = " "
            in_line = True
            i += 1
        elif ch == "/" and nxt == "*":
            chars[i] = chars[i + 1] = " "
            in_block = True
            i += 1
        i += 1
    return "".join(chars)


def _top_level_words(masked: str) -> list[str]:
    """返回括号深度为 0 的单词（大写），用于跳过 CTE 定义后定位主动词。"""
    words: list[str] = []
    depth = 0
    pos = 0
    for match in _WORD_RE.finditer(masked):
        for ch in masked[pos : match.start()]:
            if ch == "(":
                depth += 1
            elif ch == ")":
                depth = max(0, depth - 1)
        pos = match.end()
        if depth == 0:
            words.append(match.group(0).upper())
    return words


def _main_verb_after_with(masked: str) -> str:
    """WITH 语句的主动词：CTE 定义在括号内，取深度 0 的首个动词。"""
    for word in _top_level_words(masked)[1:]:
        if word in VERB_KEYWORDS:
            return word
    return ""


def _split_explain(masked: str) -> tuple[bool, str]:
    """拆出 EXPLAIN 的选项与其解释的语句，返回 (是否 ANALYZE, 内层语句)。"""
    match = _EXPLAIN_RE.match(masked)
    if match is None:
        return False, ""
    rest = masked[match.end() :]
    if _EXPLAIN_ANALYZE_RE.search(match.group(1) or ""):
        return True, rest
    analyze = _EXPLAIN_ANALYZE_RE.match(rest)
    if analyze:
        return True, rest[analyze.end() :]
    return False, rest


def classify_statement(sql: str) -> str:
    """判定语句风险等级：READ（只读）/ DML（改数据）/ DDL（改结构）。

    以首个关键字为准，并加固以下会被首个关键字误判为只读的写法：
    - ``WITH`` 开头：主语句可能是 INSERT/UPDATE/DELETE，需跳过 CTE 定义取主动词；
    - ``EXPLAIN ANALYZE``：会真正执行被解释的语句，按内层语句定级（普通 EXPLAIN/EXPLAIN PLAN 仍是只读）；
    - ``SELECT ... INTO``（建表/写文件/赋值）、``FOR UPDATE`` / ``LOCK IN SHARE MODE``（加锁读）：提升等级。
    识别不确定时一律按 DML 处理（安全侧）。
    """
    masked = _mask_literals(sql)
    first = _first_keyword(masked)
    if first == "EXPLAIN":
        analyze, inner = _split_explain(masked)
        return classify_statement(inner) if analyze else "READ"
    if first == "WITH":
        first = _main_verb_after_with(masked)
    if first in READ_KEYWORDS or first in SESSION_KEYWORDS:
        if first in READ_ESCALATION_KEYWORDS:
            for pattern, level in READ_ESCALATIONS:
                if pattern.search(masked):
                    return level
        return "READ"
    if first in DML_KEYWORDS:
        return "DML"
    if first in DDL_KEYWORDS:
        return "DDL"
    return "DML"


def format_sql(sql: str) -> str:
    try:
        return ";\n".join(transpile(sql, pretty=True) or [sql])
    except Exception:  # noqa: BLE001
        return sql


def quote_identifier(name: str, db_type: str = "") -> str:
    """按方言引用标识符（MySQL 系反引号，其余双引号）。"""
    mysql_like = db_type in ("mysql", "oceanbase", "goldendb")
    text = str(name or "").strip()
    if mysql_like:
        return "`" + text.replace("`", "``") + "`"
    return '"' + text.replace('"', '""') + '"'


def quote_value(value) -> str:
    """将 Python 值转为 SQL 字面量（用于构造安全的 DML）。"""
    if value is None:
        return "NULL"
    if isinstance(value, bool):
        return "1" if value else "0"
    if isinstance(value, (int, float)):
        return str(value)
    return "'" + str(value).replace("'", "''") + "'"


def build_connection_info(ds: DataSource) -> ConnectionInfo:
    return ConnectionInfo(
        db_type=ds.db_type,
        host=ds.host,
        port=ds.port,
        username=ds.username,
        password=decrypt_text(ds.encrypted_password),
        database_name=ds.database_name,
        ssh_enabled=ds.ssh_enabled,
        ssh_host=ds.ssh_host,
        ssh_port=ds.ssh_port,
        ssh_user=ds.ssh_user,
        ssh_auth_type=ds.ssh_auth_type,
        ssh_private_key=decrypt_text(ds.ssh_private_key),
    )


def build_adapter(ds: DataSource):
    conn = build_connection_info(ds)
    if conn.ssh_enabled and ds.db_type != "sqlite":
        local_port = get_local_port(conn)
        conn.host = "127.0.0.1"
        conn.port = local_port
    return get_adapter(conn)


def adapter_pool_key(ds: DataSource) -> tuple:
    """数据源在连接池中的桶 key：连接参数变更后按旧 key 清掉存量连接。

    与 build_adapter 的差别是不主动建立 SSH 隧道（隧道已存在时取它的本地端口）。
    隧道换端口等漏清的情况由连接池空闲 TTL / 后台 sweep 兜底。
    """
    conn = build_connection_info(ds)
    if conn.ssh_enabled and ds.db_type != "sqlite":
        local_port = existing_local_port(conn)
        if local_port:
            conn.host = "127.0.0.1"
            conn.port = local_port
    return get_adapter(conn)._conn_key()


async def build_adapter_async(ds: DataSource):
    """在线程池里构建适配器（SSH 隧道建立是阻塞操作，不能占用事件循环）。"""
    return await asyncio.to_thread(build_adapter, ds)


async def call_adapter(ds: DataSource, method: str, *args, **kwargs):
    """在线程池里连接目标库并调用适配器方法（目标库驱动均为同步实现）。"""
    adapter = await asyncio.to_thread(build_adapter, ds)
    return await asyncio.to_thread(getattr(adapter, method), *args, **kwargs)


async def get_datasource(db: AsyncSession, datasource_id: int) -> DataSource:
    ds = (await db.execute(select(DataSource).where(DataSource.id == datasource_id))).scalar_one_or_none()
    if ds is None:
        raise HTTPException(status_code=404, detail="数据源不存在")
    return ds


async def _create_execution(
    db: AsyncSession,
    sql: str,
    ds_id: int,
    statements: list[str],
    op_type: str,
    user_id: int | None,
    session_id: int | None = None,
) -> str:
    """落库暂存待确认的写操作：重启或多副本部署下确认都不会丢。"""
    execution_id = uuid.uuid4().hex
    db.add(
        PendingExecution(
            execution_id=execution_id,
            datasource_id=ds_id,
            sql_text=sql,
            statements=json.dumps(statements, ensure_ascii=False),
            operation_type=op_type,
            user_id=user_id,
            session_id=session_id,
        )
    )
    await db.commit()
    return execution_id


async def _pop_execution(db: AsyncSession, execution_id: str) -> dict:
    """取出并作废待确认记录（一次性使用），超时或不存在时报错。"""
    row = (
        await db.execute(select(PendingExecution).where(PendingExecution.execution_id == execution_id))
    ).scalar_one_or_none()
    if row is None:
        raise HTTPException(status_code=400, detail="execution_id 无效或已使用")
    expired = (datetime.now() - row.created_at).total_seconds() > EXECUTION_CONFIRM_TIMEOUT
    await db.delete(row)
    await db.commit()
    if expired:
        raise HTTPException(status_code=408, detail="确认超时，请重新执行")
    try:
        statements = json.loads(row.statements or "[]")
    except ValueError:
        statements = []
    return {
        "sql": row.sql_text,
        "datasource_id": row.datasource_id,
        "statements": statements,
        "operation_type": row.operation_type,
        "user_id": row.user_id,
        "session_id": row.session_id,
        "created_at": row.created_at.timestamp() if row.created_at else time.time(),
    }


async def cleanup_expired_executions(db: AsyncSession) -> int:
    """启动时清掉超时未确认的写操作记录，返回删除条数。"""
    cutoff = datetime.now() - timedelta(seconds=EXECUTION_CONFIRM_TIMEOUT)
    result = await db.execute(delete(PendingExecution).where(PendingExecution.created_at < cutoff))
    await db.commit()
    return result.rowcount or 0


def _serialize(value):
    if value is None:
        return None
    if isinstance(value, (str, int, float, bool)):
        return value
    if hasattr(value, "isoformat"):
        return value.isoformat()
    return str(value)


def _truncate(rows: list, columns: list, max_rows: int) -> tuple[list, bool]:
    truncated = len(rows) > max_rows
    rows = rows[:max_rows]
    if len(columns) > 50:
        columns = columns[:50]
        rows = [row[:50] for row in rows]
        truncated = True
    return rows, truncated


def _run_statements(adapter, statements: list[str], max_rows: int) -> dict:
    """顺序执行多条语句，返回最后一条查询结果或汇总。"""
    result: dict | None = None
    total_affected = 0
    duration_ms = 0
    for stmt in statements:
        start = time.time()
        res = adapter.execute(stmt)
        duration_ms = int((time.time() - start) * 1000)
        if res.get("is_query"):
            result = res
        else:
            total_affected += res.get("affected_rows", 0)
    if result is not None:
        rows, truncated = _truncate(result["rows"], result["columns"], max_rows)
        return {
            "need_confirm": False,
            "operation_type": "READ",
            "columns": result["columns"],
            "rows": [[_serialize(v) for v in row] for row in rows],
            "total_rows": len(result["rows"]),
            "page": 1,
            "page_size": max_rows,
            "duration_ms": duration_ms,
            "truncated": truncated,
            "affected_rows": total_affected,
            "message": "查询返回 " + str(len(result["rows"])) + " 行" + ("（已截断）" if truncated else ""),
        }
    return {
        "need_confirm": False,
        "operation_type": "OTHER",
        "columns": [],
        "rows": [],
        "total_rows": 0,
        "page": 1,
        "page_size": max_rows,
        "duration_ms": duration_ms,
        "truncated": False,
        "affected_rows": total_affected,
        "message": f"执行成功，影响 {total_affected} 行",
    }


async def _record_history(db: AsyncSession, ds_id: int, sql: str, status: str, row_count: int, duration_ms: int, error_message: str = "") -> None:
    db.add(
        QueryHistory(
            datasource_id=ds_id,
            sql_text=sql,
            status=status,
            row_count=row_count,
            duration_ms=duration_ms,
            error_message=error_message,
        )
    )
    await db.commit()
    # 成功执行后增量并入 few-shot 候选缓存，失败记录不进候选池、也无需清缓存
    if status == "success":
        sql_examples.record(ds_id, sql)


async def _record_audit(db: AsyncSession, user_id: int | None, action_type: str, sql: str, op_type: str, ds_id: int | None, status: str, client_ip: str = "") -> None:
    await record_audit(db, user_id, action_type, sql, op_type, ds_id, status, client_ip)


def _preview_text(adapter, statements: list[str], op_type: str) -> str:
    parts = []
    for stmt in statements:
        cls = classify_statement(stmt)
        if cls == "DDL":
            parts.append(f"DDL：{stmt[:80]}...")
        elif cls == "DML":
            try:
                if hasattr(adapter, "preview"):
                    affected = adapter.preview(stmt)
                    parts.append(f"将影响 {affected} 行数据")
                else:
                    parts.append("将执行写操作")
            except AdapterError as exc:
                parts.append(f"（无法预估影响行数：{exc}）")
    return "；".join(parts) if parts else "将执行写操作"


async def execute_sql(db: AsyncSession, ds: DataSource, sql: str, user_id: int | None, client_ip: str = "", session_id: int | None = None) -> dict:
    statements = split_statements(sql)
    if not statements:
        raise HTTPException(status_code=400, detail="SQL 为空")
    classes = [classify_statement(s) for s in statements]
    op_type = "DDL" if "DDL" in classes else ("DML" if "DML" in classes else "READ")
    try:
        await check_sql_permission(db, user_id, op_type)
    except HTTPException:
        # 鉴权失败也要留痕（与 confirm_execution 的 denied 记录保持一致）
        await _record_audit(db, user_id, "execute_sql", sql, op_type, ds.id, "denied", client_ip)
        SQL_EXECUTIONS.labels(operation_type=op_type, status="denied").inc()
        raise
    adapter = await build_adapter_async(ds)
    start = time.time()

    if op_type == "READ":
        try:
            result = await asyncio.to_thread(_run_statements, adapter, statements, MAX_ROWS_PER_PAGE)
            duration_ms = int((time.time() - start) * 1000)
            result["duration_ms"] = duration_ms
            await _record_history(db, ds.id, sql, "success", result.get("total_rows", 0), duration_ms)
            await _record_audit(db, user_id, "execute_sql", sql, "READ", ds.id, "success", client_ip)
            SQL_EXECUTIONS.labels(operation_type="READ", status="success").inc()
            return result
        except AdapterError as exc:
            duration_ms = int((time.time() - start) * 1000)
            await _record_history(db, ds.id, sql, "failed", 0, duration_ms, str(exc))
            await _record_audit(db, user_id, "execute_sql", sql, "READ", ds.id, "failed", client_ip)
            SQL_EXECUTIONS.labels(operation_type="READ", status="failed").inc()
            raise HTTPException(status_code=400, detail=str(exc)) from exc

    risk_level = "danger" if op_type == "DDL" else "warning"
    execution_id = await _create_execution(db, sql, ds.id, statements, op_type, user_id, session_id)
    try:
        preview = await asyncio.to_thread(_preview_text, adapter, statements, op_type)
    except Exception:  # noqa: BLE001
        preview = "将执行写操作"
    await _record_audit(db, user_id, "execute_sql", sql, op_type, ds.id, "pending", client_ip)
    SQL_EXECUTIONS.labels(operation_type=op_type, status="pending").inc()
    return {
        "need_confirm": True,
        "operation_type": op_type,
        "sql_text": sql,
        "preview": preview,
        "risk_level": risk_level,
        "execution_id": execution_id,
        "session_id": session_id,
    }


async def confirm_execution(db: AsyncSession, execution_id: str, confirmed: bool, client_ip: str = "") -> dict:
    entry = await _pop_execution(db, execution_id)
    if not confirmed:
        await _record_audit(db, entry.get("user_id"), "execute_sql", entry["sql"], entry["operation_type"], entry.get("datasource_id"), "rejected", client_ip)
        SQL_EXECUTIONS.labels(operation_type=entry["operation_type"], status="rejected").inc()
        return {"status": "cancelled", "message": "已取消执行", "session_id": entry.get("session_id")}
    try:
        await check_sql_permission(db, entry.get("user_id"), entry["operation_type"])
    except HTTPException:
        await _record_audit(db, entry.get("user_id"), "execute_sql", entry["sql"], entry["operation_type"], entry.get("datasource_id"), "denied", client_ip)
        SQL_EXECUTIONS.labels(operation_type=entry["operation_type"], status="denied").inc()
        raise
    ds = await get_datasource(db, entry["datasource_id"])
    adapter = await build_adapter_async(ds)
    start = time.time()
    try:
        result = await asyncio.to_thread(_run_statements, adapter, entry["statements"], MAX_ROWS_PER_PAGE)
        duration_ms = int((time.time() - start) * 1000)
        result["duration_ms"] = duration_ms
        affected = result.get("affected_rows", 0)
        await _record_history(db, ds.id, entry["sql"], "success", affected, duration_ms)
        await _record_audit(db, entry.get("user_id"), "execute_sql", entry["sql"], entry["operation_type"], ds.id, "approved", client_ip)
        SQL_EXECUTIONS.labels(operation_type=entry["operation_type"], status="executed").inc()
        result["session_id"] = entry.get("session_id")
        result["status"] = "executed"
        return result
    except AdapterError as exc:
        duration_ms = int((time.time() - start) * 1000)
        await _record_history(db, ds.id, entry["sql"], "failed", 0, duration_ms, str(exc))
        await _record_audit(db, entry.get("user_id"), "execute_sql", entry["sql"], entry["operation_type"], ds.id, "failed", client_ip)
        SQL_EXECUTIONS.labels(operation_type=entry["operation_type"], status="failed").inc()
        raise HTTPException(status_code=400, detail=str(exc)) from exc
