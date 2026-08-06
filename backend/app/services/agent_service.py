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
from ..models import AIConfig, AgentMessage, AgentSession, AuditLog, DataSource
from .llm_providers import LLMError, build_messages, get_llm_provider
from .sql_service import (
    MAX_ROWS_PER_PAGE,
    build_adapter,
    classify_statement,
    execute_sql,
    split_statements,
)

SYSTEM_TEMPLATE = """你是数据库 Agent 助手，运行在数据库查询工具中，使用中文回复。
当前数据库 Schema 摘要：
{schema}

请严格输出 JSON（不要包含其他内容、不要使用 Markdown 代码块），格式：
{{"thought": "你的推理过程（中文）", "sql": "需要执行的SQL；无需SQL时为空字符串", "answer": "无需SQL时的直接回答（中文）"}}
规则：
- 用户要求查询或操作数据时生成 SQL，否则 answer 直接回答
- SQL 必须针对上述 Schema 中存在的表名与列名
- 查询使用 SELECT；写操作（INSERT/UPDATE/DELETE 或 DDL）也生成完整 SQL，将由系统安全确认后执行"""

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


def _schema_summary(db_session: AsyncSession, ds: DataSource | None) -> str:
    if ds is None:
        return "（未选择数据源）"
    try:
        adapter = build_adapter(ds)
        return adapter.schema_summary()[:8000]
    except Exception:  # noqa: BLE001
        return "（Schema 获取失败）"


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
        yield {"type": "error", "content": "未配置可用的 AI 模型，请到 系统设置 → AI 配置 中添加模型"}
        yield {"type": "done"}
        return

    db.add(AgentMessage(session_id=session.id, role="user", content=message, message_type="text"))
    session.message_count = (session.message_count or 0) + 1
    await db.commit()

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
    schema = _schema_summary(db, ds)
    history = await _load_history(db, session.id)
    system = SYSTEM_TEMPLATE.format(schema=schema)
    messages = build_messages(system, history, message)

    try:
        raw = await provider.chat(messages, json_mode=True)
        parsed = _extract_json(raw)
    except (LLMError, ValueError, json.JSONDecodeError) as exc:
        await _record_audit(db, user_id, "agent_action", message, "AGENT", ds.id if ds else None, "failed", client_ip)
        yield {"type": "error", "content": f"AI 调用失败: {exc}"}
        yield {"type": "done"}
        return

    thought = str(parsed.get("thought") or "").strip()
    sql = str(parsed.get("sql") or "").strip()
    answer = str(parsed.get("answer") or "").strip()

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
        try:
            result = await execute_sql(db, ds, sql, user_id, client_ip, session_id=session.id)
        except HTTPException as exc:
            yield {"type": "error", "content": str(exc.detail)}
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
    schema = _schema_summary(db, ds)
    prompt = f"当前数据库 Schema：\n{schema}\n\n请用中文解释以下 SQL 的含义、执行逻辑与潜在风险：\n{sql}"
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
