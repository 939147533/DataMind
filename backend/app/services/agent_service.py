"""AI Agent 服务：会话管理、NL→SQL、SSE 事件流。"""
import json
import time
import uuid
from datetime import datetime
from typing import AsyncIterator

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ..adapters import AdapterError
from ..models import AIConfig, AgentMessage, AgentSession, AuditLog, DataSource, QueryHistory
from .llm_providers import LLMError, build_messages, get_llm_provider
from .sql_service import (
    MAX_ROWS_PER_PAGE,
    build_adapter,
    classify_statement,
    execute_sql,
    split_statements,
)

SYSTEM_TEMPLATE = """你是数据库 Agent 助手，运行在数据库查询工具中，使用中文回复。
当前数据库类型：{db_type}
{dialect_hint}
当前数据库 Schema 摘要：
{schema}
{few_shots}
当 Schema 摘要不足以回答时，可先调用工具获取更多信息。工具调用输出格式（JSON）：
{{"tool": "list_tables|get_columns|sample_data|explain", "tool_params": {{"table": "表名", "schema": "Schema名", "sql": "SQL", "limit": 5}}}}
工具说明：
- list_tables：列出数据表；tool_params 可选 schema
- get_columns：查看表结构；tool_params 需要 table
- sample_data：采样表数据；tool_params 需要 table，可选 limit（默认 5）
- explain：查看 SQL 执行计划；tool_params 需要 sql
工具结果会追加给你，请根据工具结果继续思考，直到最终输出最终 JSON。

请严格输出 JSON（不要包含其他内容、不要使用 Markdown 代码块），最终格式：
{{"thought": "你的推理过程（中文）", "sql": "需要执行的SQL；无需SQL时为空字符串", "answer": "无需SQL时的直接回答（中文）", "chart": "可选：用户要求生成图表时输出图表配置，否则省略该字段"}}
chart 配置格式：{{"type": "bar|line|pie", "title": "图表标题", "x_column": "X 轴列名", "y_columns": ["数值列1", "数值列2", ...], "aggregation": "none|sum|count|avg|max|min"}}
规则：
- 用户要求查询或操作数据时生成 SQL，否则 answer 直接回答
- SQL 必须针对 Schema 中存在的表名与列名，遵循当前数据库方言语法
- 文本枚举列（如状态、类型、渠道）通常存储英文取值（如 SUCCESS/FAIL/PENDING），比较时使用 UPPER(列)=UPPER('值') 或直接使用 Schema 摘要中的枚举值，禁止用中文猜测
- 查询使用 SELECT；写操作（INSERT/UPDATE/DELETE 或 DDL）也生成完整 SQL，将由系统安全确认后执行
- 用户要求可视化/图表时，SQL 使用 GROUP BY 聚合查询，并同时输出 chart 配置；单指标可用 y_column，多指标（如笔数和金额）用 y_columns 数组；x_column/y_columns 必须是查询结果中的列名"""

SUMMARY_TEMPLATE = """你是数据库 Agent 助手。用户提问：{question}
你执行的 SQL：{sql}
查询结果：列 {columns}，共 {total} 行
前 {shown} 行数据：
{rows_preview}
请用简洁中文总结结果，包含关键数字与结论。"""


async def _get_session(db: AsyncSession, session_id: int | None) -> AgentSession:
    if session_id is None:
        raise HTTPException(status_code=400, detail="缺少会话 ID")
    session = (await db.execute(select(AgentSession).where(AgentSession.id == session_id))).scalar_one_or_none()
    if session is None:
        raise HTTPException(status_code=404, detail="会话不存在")
    return session


async def resolve_model_config(db: AsyncSession, session: AgentSession | None, model_config_id: int | None) -> AIConfig | None:
    if model_config_id:
        cfg = (await db.execute(select(AIConfig).where(AIConfig.id == model_config_id))).scalar_one_or_none()
        if cfg and cfg.is_active:
            return cfg
    if session and session.model_config_id:
        cfg = (await db.execute(select(AIConfig).where(AIConfig.id == session.model_config_id))).scalar_one_or_none()
        if cfg and cfg.is_active:
            return cfg
    cfg = (await db.execute(select(AIConfig).where(AIConfig.is_default.is_(True), AIConfig.is_active.is_(True)))).scalars().first()
    if cfg:
        return cfg
    cfg = (await db.execute(select(AIConfig).where(AIConfig.is_active.is_(True)))).scalars().first()
    return cfg


async def create_session(db: AsyncSession, datasource_id: int | None, model_config_id: int | None, title: str) -> AgentSession:
    session = AgentSession(datasource_id=datasource_id, model_config_id=model_config_id, title=title or "新对话")
    db.add(session)
    await db.commit()
    await db.refresh(session)
    return session


async def list_sessions(db: AsyncSession) -> list[dict]:
    rows = (await db.execute(select(AgentSession).order_by(AgentSession.updated_at.desc()).limit(100))).scalars().all()
    return [
        {
            "id": s.id,
            "title": s.title,
            "datasource_id": s.datasource_id,
            "model_config_id": s.model_config_id,
            "message_count": s.message_count,
            "created_at": s.created_at.isoformat() if s.created_at else None,
            "updated_at": s.updated_at.isoformat() if s.updated_at else None,
        }
        for s in rows
    ]


async def delete_session(db: AsyncSession, session_id: int) -> None:
    session = await _get_session(db, session_id)
    await db.execute(AgentMessage.__table__.delete().where(AgentMessage.session_id == session_id))
    await db.delete(session)
    await db.commit()


async def list_messages(db: AsyncSession, session_id: int) -> list[dict]:
    rows = (
        await db.execute(
            select(AgentMessage).where(AgentMessage.session_id == session_id).order_by(AgentMessage.id.asc())
        )
    ).scalars().all()
    return [
        {
            "id": m.id,
            "role": m.role,
            "content": m.content,
            "message_type": m.message_type,
            "created_at": m.created_at.isoformat() if m.created_at else None,
        }
        for m in rows
    ]


async def _load_history(db: AsyncSession, session_id: int, limit: int = 10) -> list[dict]:
    rows = (
        await db.execute(
            select(AgentMessage)
            .where(AgentMessage.session_id == session_id, AgentMessage.role.in_(["user", "assistant"]))
            .order_by(AgentMessage.id.desc())
            .limit(limit)
        )
    ).scalars().all()
    history: list[dict] = []
    for m in reversed(rows):
        if m.message_type in ("text", "sql"):
            history.append({"role": m.role, "content": m.content[:2000]})
    return history


def _schema_info(db_session: AsyncSession, ds: DataSource | None) -> dict:
    if ds is None:
        return {"schema": "（未选择数据源）", "db_type": "", "dialect_hint": ""}
    db_type = getattr(ds, "db_type", "") or ""
    try:
        adapter = build_adapter(ds)
        return {
            "schema": adapter.schema_summary()[:8000],
            "db_type": getattr(adapter, "db_type", db_type),
            "dialect_hint": getattr(adapter, "dialect_hint", "") or "",
        }
    except Exception:  # noqa: BLE001
        return {"schema": "（Schema 获取失败）", "db_type": db_type, "dialect_hint": ""}


def _extract_json(text: str) -> dict:
    text = text.strip()
    if text.startswith("```"):
        text = text.strip("`")
        if text.startswith("json"):
            text = text[4:]
    start, end = text.find("{"), text.rfind("}")
    if start < 0 or end < start:
        raise ValueError("模型未返回 JSON")
    return json.loads(text[start : end + 1])


def _truncate_result(columns: list, rows: list) -> tuple[list, list, int, bool]:
    total = len(rows)
    truncated = False
    if total > 100:
        rows = rows[:100]
        truncated = True
    if len(columns) > 50:
        columns = columns[:50]
        rows = [r[:50] for r in rows]
        truncated = True
    return columns, rows, total, truncated


CHART_TYPES = ("bar", "line", "pie")
AGGREGATIONS = ("none", "sum", "count", "avg", "max", "min")


def _parse_chart(raw) -> dict | None:
    """校验并规范化模型输出的图表配置，非法则返回 None；支持单/多系列。"""
    if not isinstance(raw, dict):
        return None
    chart_type = str(raw.get("type") or "").lower()
    if chart_type not in CHART_TYPES:
        return None
    x_column = str(raw.get("x_column") or "").strip()
    if not x_column:
        return None
    y_raw = raw.get("y_columns") or raw.get("y_column") or ""
    if isinstance(y_raw, list):
        y_columns = [str(c).strip() for c in y_raw if str(c).strip()]
    else:
        y_columns = [c.strip() for c in str(y_raw).split(",") if c.strip()]
    if not y_columns:
        return None
    aggregation = str(raw.get("aggregation") or "none").lower()
    if aggregation not in AGGREGATIONS:
        aggregation = "none"
    return {
        "chart_type": chart_type,
        "title": str(raw.get("title") or "").strip(),
        "x_column": x_column,
        "y_column": ", ".join(y_columns),
        "aggregation": aggregation,
    }



def _make_title(message: str, max_len: int = 20) -> str:
    # 以问题的概括作为对话名称：清洗开头装饰后截取前 N 个字符
    text = message.strip()
    while text:
        ch = text[0]
        code = ord(ch)
        if code > 0xFFFF or 0x1F000 <= code <= 0x1FAFF:
            text = text[1:].lstrip()
            continue
        if 0x2600 <= code <= 0x27BF or 0x2B00 <= code <= 0x2BFF or ch in "#*>-·—• ":
            text = text[1:].lstrip()
            continue
        break
    text = " ".join(text.split())
    if not text:
        return "新对话"
    if len(text) > max_len:
        return text[:max_len] + "…"
    return text


MAX_TOOL_ROUNDS = 3
TOOL_NAMES = ("list_tables", "get_columns", "sample_data", "explain")


async def _load_few_shots(db: AsyncSession, ds_id: int | None, limit: int = 3) -> str:
    """从执行历史中挑选近期成功的只读 SQL，作为模型 few-shot 风格示例。"""
    if not ds_id:
        return ""
    rows = (
        await db.execute(
            select(QueryHistory)
            .where(QueryHistory.datasource_id == ds_id, QueryHistory.status == "success")
            .order_by(QueryHistory.id.desc())
            .limit(60)
        )
    ).scalars().all()
    seen: set[str] = set()
    examples: list[str] = []
    for r in rows:
        sql = (r.sql_text or "").strip()
        if not sql or sql in seen or len(sql) > 400:
            continue
        seen.add(sql)
        examples.append(sql)
        if len(examples) >= limit:
            break
    if not examples:
        return ""
    return "历史成功执行的 SQL 示例（仅供风格参考）：\n" + "\n".join(examples)


def _run_tool(ds: DataSource, tool_name: str, params: dict) -> str:
    """执行 Agent 元数据工具（同步适配器调用，结果转文本）。"""
    from ..adapters import AdapterError

    adapter = build_adapter(ds)
    schema = str(params.get("schema") or "").strip()
    table = str(params.get("table") or "").strip()
    try:
        if tool_name == "list_tables":
            tables = adapter.get_tables(schema)
            return "数据表列表：" + ("、".join(tables) if tables else "（空）")
        if tool_name == "get_columns":
            if not table:
                return "错误：get_columns 需要 table 参数"
            cols = adapter.get_table_columns(table, schema)
            if not cols:
                return f"表 {table} 不存在或无列信息"
            lines = [f"{c['name']} {c['data_type']}{' PK' if c.get('primary_key') else ''}" for c in cols]
            return f"表 {schema + '.' if schema else ''}{table} 列：\n" + "\n".join(lines)
        if tool_name == "sample_data":
            if not table:
                return "错误：sample_data 需要 table 参数"
            limit = int(params.get("limit") or 5)
            data = adapter.get_table_data(table, schema, 1, min(max(limit, 1), 20))
            cols = data.get("columns") or []
            rows = data.get("rows") or []
            lines = [" | ".join(str(v) for v in row) for row in rows[: limit]]
            return f"表 {table} 前 {len(lines)} 行（列：{', '.join(cols)}）：\n" + "\n".join(lines)
        if tool_name == "explain":
            sql = str(params.get("sql") or "").strip()
            if not sql:
                return "错误：explain 需要 sql 参数"
            plan = adapter.explain(sql)
            return "执行计划：\n" + "\n".join(
                str(r.get("detail") or r) for r in plan[:20]
            )
    except AdapterError as exc:
        return f"工具执行失败：{exc}"
    except Exception as exc:  # noqa: BLE001
        return f"工具执行异常：{exc}"
    return f"未知工具：{tool_name}"


async def agent_chat(
    db: AsyncSession,
    session_id: int | None,
    datasource_id: int | None,
    model_config_id: int | None,
    message: str,
    user_id: int,
    client_ip: str = "",
) -> AsyncIterator[dict]:
    session = await _get_session(db, session_id)
    if datasource_id is None:
        datasource_id = session.datasource_id
    ds = None
    if datasource_id:
        ds = (await db.execute(select(DataSource).where(DataSource.id == datasource_id))).scalar_one_or_none()
    config = await resolve_model_config(db, session, model_config_id)
    if config is None:
        yield {"type": "error", "content": "未配置可用的 AI 模型，请到 系统设置 → 大模型连接配置 中添加模型"}
        yield {"type": "done"}
        return

    is_first_message = (session.message_count or 0) == 0
    db.add(AgentMessage(session_id=session.id, role="user", content=message, message_type="text"))
    session.message_count = (session.message_count or 0) + 1
    if is_first_message:
        session.title = _make_title(message)
    await db.commit()
    if is_first_message:
        yield {"type": "session_title", "content": session.title}

    provider = get_llm_provider(config)
    validate = getattr(provider, "validate", None)
    if validate is not None:
        try:
            validate()
        except LLMError as exc:
            await _record_audit(db, user_id, "agent_action", message, "AGENT", ds.id if ds else None, "failed", client_ip)
            yield {"type": "error", "content": f"AI 调用失败: {exc}"}
            yield {"type": "done"}
            return
    schema_info = _schema_info(db, ds)
    history = await _load_history(db, session.id)
    system = SYSTEM_TEMPLATE.format(
        db_type=schema_info["db_type"],
        dialect_hint=schema_info["dialect_hint"],
        schema=schema_info["schema"],
        few_shots=await _load_few_shots(db, ds.id if ds else None),
    )
    messages = build_messages(system, history, message)

    try:
        raw = await provider.chat(messages, json_mode=True)
        parsed = _extract_json(raw)
    except (LLMError, ValueError, json.JSONDecodeError) as exc:
        await _record_audit(db, user_id, "agent_action", message, "AGENT", ds.id if ds else None, "failed", client_ip)
        yield {"type": "error", "content": f"AI 调用失败: {exc}"}
        yield {"type": "done"}
        return

    # 工具调用循环：模型可先请求元数据工具，工具结果追加后继续
    for _round in range(MAX_TOOL_ROUNDS):
        tool_name = str(parsed.get("tool") or "").strip()
        if tool_name not in TOOL_NAMES:
            break
        if ds is None:
            yield {"type": "error", "content": "未选择数据源，无法调用工具"}
            break
        tool_params = parsed.get("tool_params") or {}
        tool_result = _run_tool(ds, tool_name, tool_params)
        yield {"type": "tool", "tool": tool_name, "content": tool_result}
        messages.append(
            {
                "role": "user",
                "content": f"工具 {tool_name} 返回：\n{tool_result}\n请基于该结果继续（可再次调用工具，或直接输出最终 JSON）。",
            }
        )
        try:
            raw = await provider.chat(messages, json_mode=True)
            parsed = _extract_json(raw)
        except (LLMError, ValueError, json.JSONDecodeError) as exc:
            yield {"type": "error", "content": f"AI 调用失败: {exc}"}
            yield {"type": "done"}
            return
    else:
        yield {"type": "error", "content": "工具调用轮次过多，已停止"}
        yield {"type": "done"}
        return

    thought = str(parsed.get("thought") or "").strip()
    sql = str(parsed.get("sql") or "").strip()
    answer = str(parsed.get("answer") or "").strip()
    chart = None

    if thought:
        yield {"type": "thought", "content": thought}

    if not sql:
        final_text = answer or "已完成。"
        yield {"type": "text", "content": final_text}
        db.add(AgentMessage(session_id=session.id, role="assistant", content=final_text, message_type="text"))
        session.message_count = (session.message_count or 0) + 1
        await db.commit()
        await _record_audit(db, user_id, "agent_action", message, "AGENT", ds.id if ds else None, "success", client_ip)
        yield {"type": "done"}
        return

    # 有 SQL
    statements = split_statements(sql)
    op_type = "DDL" if any(classify_statement(s) == "DDL" for s in statements) else ("DML" if any(classify_statement(s) == "DML" for s in statements) else "READ")
    yield {"type": "sql", "content": sql, "operation_type": op_type, "need_confirm": op_type != "READ"}

    if op_type == "READ":
        result = None
        error_detail = ""
        for attempt in range(3):
            try:
                result = await execute_sql(db, ds, sql, user_id, client_ip, session_id=session.id)
                break
            except HTTPException as exc:
                error_detail = str(exc.detail)
                if attempt >= 2:
                    break
                yield {"type": "retry", "content": f"SQL 执行失败（{error_detail}），AI 正在修正重试…"}
                messages.append(
                    {
                        "role": "user",
                        "content": f"你生成的 SQL 执行失败：{error_detail}\n请修正 SQL 后直接输出最终 JSON（不要再调用工具）。原 SQL：\n{sql}",
                    }
                )
                try:
                    raw = await provider.chat(messages, json_mode=True)
                    parsed = _extract_json(raw)
                except (LLMError, ValueError, json.JSONDecodeError) as exc:
                    yield {"type": "error", "content": f"AI 修正失败: {exc}"}
                    yield {"type": "done"}
                    return
                new_sql = str(parsed.get("sql") or "").strip()
                if not new_sql or new_sql == sql:
                    break
                sql = new_sql
                yield {"type": "sql", "content": sql, "operation_type": "READ", "need_confirm": False}
        if result is None:
            yield {"type": "error", "content": error_detail or "SQL 执行失败"}
            yield {"type": "done"}
            return
        columns = result.get("columns", [])
        rows = result.get("rows", [])
        columns, rows, total, truncated = _truncate_result(columns, rows)
        yield {
            "type": "result",
            "content": {
                "columns": columns,
                "rows": rows,
                "total_rows": result.get("total_rows", total),
                "duration_ms": result.get("duration_ms", 0),
                "sql_text": sql,
            },
            "truncated": truncated,
        }
        chart = _parse_chart(parsed.get("chart"))
        if chart:
            yield {"type": "chart", "content": chart}
        summary_messages = build_messages(
            "",
            [],
            SUMMARY_TEMPLATE.format(
                question=message,
                sql=sql,
                columns=columns,
                total=total,
                shown=len(rows),
                rows_preview=json.dumps(rows[:10], ensure_ascii=False)[:4000],
            ),
        )
        try:
            final_text = ""
            async for chunk in provider.stream(summary_messages):
                final_text += chunk
                yield {"type": "text", "content": chunk}
        except LLMError as exc:
            final_text = f"（结果已返回，但总结失败：{exc}）"
            yield {"type": "text", "content": final_text}
        if not final_text.strip():
            final_text = "查询已完成。"
        db.add(AgentMessage(session_id=session.id, role="assistant", content=sql, message_type="sql"))
        db.add(AgentMessage(session_id=session.id, role="assistant", content=final_text, message_type="text"))
        if chart:
            chart_content = json.dumps(
                {
                    "chart": chart,
                    "result": {
                        "columns": columns,
                        "rows": rows,
                        "total_rows": result.get("total_rows", total),
                        "duration_ms": result.get("duration_ms", 0),
                        "sql_text": sql,
                    },
                },
                ensure_ascii=False,
            )
            db.add(AgentMessage(session_id=session.id, role="assistant", content=chart_content, message_type="chart"))
            session.message_count = (session.message_count or 0) + 1
        session.message_count = (session.message_count or 0) + 2
        await db.commit()
        yield {"type": "done"}
        return

    # 写操作：走授权确认
    try:
        confirm_result = await execute_sql(db, ds, sql, user_id, client_ip, session_id=session.id)
    except HTTPException as exc:
        yield {"type": "error", "content": str(exc.detail)}
        yield {"type": "done"}
        return
    if confirm_result.get("need_confirm"):
        yield {
            "type": "authorization_required",
            "execution_id": confirm_result["execution_id"],
            "sql_text": sql,
            "operation_type": confirm_result["operation_type"],
            "risk_level": confirm_result["risk_level"],
            "preview": confirm_result.get("preview", ""),
            "session_id": session.id,
        }
    yield {"type": "done"}


async def agent_confirm(db: AsyncSession, execution_id: str, confirmed: bool, client_ip: str = "") -> dict:
    from .sql_service import confirm_execution

    return await confirm_execution(db, execution_id, confirmed, client_ip)


async def explain_sql(db: AsyncSession, datasource_id: int | None, sql: str, user_id: int) -> AsyncIterator[dict]:
    config = await resolve_model_config(db, None, None)
    if config is None:
        yield {"type": "error", "content": "未配置可用的 AI 模型"}
        return
    ds = None
    if datasource_id:
        ds = (await db.execute(select(DataSource).where(DataSource.id == datasource_id))).scalar_one_or_none()
    schema_info = _schema_info(db, ds)
    prompt = f"当前数据库类型：{schema_info['db_type']}\n{schema_info['dialect_hint']}\n当前数据库 Schema：\n{schema_info['schema']}\n\n请用中文解释以下 SQL 的含义、执行逻辑与潜在风险：\n{sql}"
    provider = get_llm_provider(config)
    try:
        async for chunk in provider.stream(build_messages("你是 SQL 解释专家。", [], prompt)):
            yield {"type": "text", "content": chunk}
    except LLMError as exc:
        yield {"type": "error", "content": str(exc)}


async def optimize_sql(db: AsyncSession, datasource_id: int | None, sql: str, user_id: int) -> AsyncIterator[dict]:
    config = await resolve_model_config(db, None, None)
    if config is None:
        yield {"type": "error", "content": "未配置可用的 AI 模型"}
        return
    plan = ""
    ds = None
    if datasource_id:
        ds = (await db.execute(select(DataSource).where(DataSource.id == datasource_id))).scalar_one_or_none()
        if ds:
            try:
                plan = str(build_adapter(ds).explain(sql)[:20])
            except Exception:  # noqa: BLE001
                plan = ""
    prompt = f"SQL：\n{sql}\n\n执行计划：\n{plan}\n\n请给出优化建议（索引、查询重写、性能风险），用中文简洁列出。"
    provider = get_llm_provider(config)
    try:
        async for chunk in provider.stream(build_messages("你是 SQL 性能优化专家。", [], prompt)):
            yield {"type": "text", "content": chunk}
    except LLMError as exc:
        yield {"type": "error", "content": str(exc)}


async def _record_audit(db: AsyncSession, user_id: int, action_type: str, sql: str, op_type: str, ds_id: int | None, status: str, client_ip: str) -> None:
    db.add(
        AuditLog(
            user_id=user_id,
            action_type=action_type,
            sql_text=sql[:4000],
            operation_type=op_type,
            datasource_id=ds_id,
            status=status,
            client_ip=client_ip,
        )
    )
    await db.commit()


async def save_chart(db: AsyncSession, user_id: int, data) -> dict:
    """保存 Agent 生成的图表到可视化报表模块。"""
    from ..models import Chart

    if data.datasource_id:
        ds = (await db.execute(select(DataSource).where(DataSource.id == data.datasource_id))).scalar_one_or_none()
        if ds is None:
            raise HTTPException(status_code=404, detail="数据源不存在")
    chart = Chart(
        name=data.name,
        datasource_id=data.datasource_id,
        sql_text=data.sql_text,
        chart_type=data.chart_type,
        x_column=data.x_column,
        y_column=data.y_column,
        aggregation=data.aggregation,
        options=data.options or "{}",
    )
    db.add(chart)
    await db.commit()
    await db.refresh(chart)
    await _record_audit(db, user_id, "chart_manage", data.sql_text, "CHART", data.datasource_id, "success", "")
    return {
        "id": chart.id,
        "name": chart.name,
        "datasource_id": chart.datasource_id,
        "sql_text": chart.sql_text,
        "chart_type": chart.chart_type,
        "x_column": chart.x_column,
        "y_column": chart.y_column,
        "aggregation": chart.aggregation,
        "options": chart.options,
        "created_at": chart.created_at.isoformat() if chart.created_at else None,
    }
