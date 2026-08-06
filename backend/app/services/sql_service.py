"""SQL 执行服务：拆分、分类、授权、执行、确认、历史、审计。"""
import time
import uuid
from datetime import datetime, timedelta

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlglot import transpile

from ..adapters import AdapterError, get_adapter
from ..adapters.base import ConnectionInfo
from ..config import EXECUTION_CONFIRM_TIMEOUT, MAX_ROWS_PER_PAGE
from ..models import AuditLog, DataSource, QueryHistory
from ..security import decrypt_text
from .ssh_tunnel import get_local_port

READ_KEYWORDS = {"SELECT", "WITH", "SHOW", "DESC", "DESCRIBE", "EXPLAIN", "PRAGMA", "VALUES"}
SESSION_KEYWORDS = {"SET", "USE", "BEGIN", "COMMIT", "START"}
DML_KEYWORDS = {"INSERT", "UPDATE", "DELETE", "MERGE", "REPLACE", "UPSERT", "CALL"}
DDL_KEYWORDS = {"CREATE", "ALTER", "DROP", "TRUNCATE", "RENAME", "GRANT", "REVOKE"}

_executions: dict[str, dict] = {}


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
        else:
            break
    match = text.split(None, 1)
    return match[0].upper() if match else ""


def classify_statement(sql: str) -> str:
    first = _first_keyword(sql)
    if first in READ_KEYWORDS or first in SESSION_KEYWORDS:
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


async def get_datasource(db: AsyncSession, datasource_id: int) -> DataSource:
    ds = (await db.execute(select(DataSource).where(DataSource.id == datasource_id))).scalar_one_or_none()
    if ds is None:
        raise HTTPException(status_code=404, detail="数据源不存在")
    return ds


def _create_execution(sql: str, ds_id: int, statements: list[str], op_type: str, user_id: int | None, session_id: int | None = None) -> str:
    execution_id = uuid.uuid4().hex
    _executions[execution_id] = {
        "sql": sql,
        "datasource_id": ds_id,
        "statements": statements,
        "operation_type": op_type,
        "user_id": user_id,
        "session_id": session_id,
        "created_at": time.time(),
    }
    return execution_id


def _pop_execution(execution_id: str) -> dict:
    entry = _executions.pop(execution_id, None)
    if entry is None:
        raise HTTPException(status_code=400, detail="execution_id 无效或已使用")
    if time.time() - entry["created_at"] > EXECUTION_CONFIRM_TIMEOUT:
        raise HTTPException(status_code=408, detail="确认超时，请重新执行")
    return entry


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


async def _record_audit(db: AsyncSession, user_id: int | None, action_type: str, sql: str, op_type: str, ds_id: int | None, status: str, client_ip: str = "") -> None:
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
    adapter = build_adapter(ds)
    start = time.time()

    if op_type == "READ":
        try:
            result = _run_statements(adapter, statements, MAX_ROWS_PER_PAGE)
            duration_ms = int((time.time() - start) * 1000)
            result["duration_ms"] = duration_ms
            await _record_history(db, ds.id, sql, "success", result.get("total_rows", 0), duration_ms)
            await _record_audit(db, user_id, "execute_sql", sql, "READ", ds.id, "success", client_ip)
            return result
        except AdapterError as exc:
            duration_ms = int((time.time() - start) * 1000)
            await _record_history(db, ds.id, sql, "failed", 0, duration_ms, str(exc))
            await _record_audit(db, user_id, "execute_sql", sql, "READ", ds.id, "failed", client_ip)
            raise HTTPException(status_code=400, detail=str(exc))

    risk_level = "danger" if op_type == "DDL" else "warning"
    execution_id = _create_execution(sql, ds.id, statements, op_type, user_id, session_id)
    try:
        preview = _preview_text(adapter, statements, op_type)
    except Exception:  # noqa: BLE001
        preview = "将执行写操作"
    await _record_audit(db, user_id, "execute_sql", sql, op_type, ds.id, "pending", client_ip)
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
    entry = _pop_execution(execution_id)
    if not confirmed:
        await _record_audit(db, entry.get("user_id"), "execute_sql", entry["sql"], entry["operation_type"], entry.get("datasource_id"), "rejected", client_ip)
        return {"status": "cancelled", "message": "已取消执行", "session_id": entry.get("session_id")}
    ds = await get_datasource(db, entry["datasource_id"])
    adapter = build_adapter(ds)
    start = time.time()
    try:
        result = _run_statements(adapter, entry["statements"], MAX_ROWS_PER_PAGE)
        duration_ms = int((time.time() - start) * 1000)
        result["duration_ms"] = duration_ms
        affected = result.get("affected_rows", 0)
        await _record_history(db, ds.id, entry["sql"], "success", affected, duration_ms)
        await _record_audit(db, entry.get("user_id"), "execute_sql", entry["sql"], entry["operation_type"], ds.id, "approved", client_ip)
        result["session_id"] = entry.get("session_id")
        result["status"] = "executed"
        return result
    except AdapterError as exc:
        duration_ms = int((time.time() - start) * 1000)
        await _record_history(db, ds.id, entry["sql"], "failed", 0, duration_ms, str(exc))
        await _record_audit(db, entry.get("user_id"), "execute_sql", entry["sql"], entry["operation_type"], ds.id, "failed", client_ip)
        raise HTTPException(status_code=400, detail=str(exc))
