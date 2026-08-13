"""审计日志：导出与保留策略清理。"""
import csv
import io
from datetime import datetime, timedelta

from fastapi import HTTPException
from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from ..models import AuditLog


def _serialize(value):
    if value is None:
        return ""
    if hasattr(value, "isoformat"):
        return value.isoformat()
    return value


async def _query_rows(db: AsyncSession, action_type: str = "", status: str = "", limit: int = 5000) -> list[dict]:
    query = select(AuditLog).order_by(AuditLog.id.desc()).limit(limit)
    if action_type:
        query = query.where(AuditLog.action_type == action_type)
    if status:
        query = query.where(AuditLog.status == status)
    rows = (await db.execute(query)).scalars().all()
    return [
        {
            "id": r.id,
            "user_id": r.user_id,
            "action_type": r.action_type,
            "sql_text": r.sql_text,
            "operation_type": r.operation_type,
            "datasource_id": r.datasource_id,
            "status": r.status,
            "client_ip": r.client_ip,
            "created_at": r.created_at.isoformat() if r.created_at else "",
        }
        for r in rows
    ]


def export_audit_csv(items: list[dict]) -> bytes:
    buf = io.StringIO()
    writer = csv.writer(buf)
    writer.writerow(["id", "user_id", "action_type", "sql_text", "operation_type", "datasource_id", "status", "client_ip", "created_at"])
    for it in items:
        writer.writerow([_serialize(it.get(k)) for k in ("id", "user_id", "action_type", "sql_text", "operation_type", "datasource_id", "status", "client_ip", "created_at")])
    return ("\ufeff" + buf.getvalue()).encode("utf-8")


def export_audit_excel(items: list[dict]) -> bytes:
    from openpyxl import Workbook

    wb = Workbook()
    ws = wb.active
    ws.title = "审计日志"
    headers = ["ID", "用户ID", "动作类型", "SQL", "操作类型", "数据源ID", "状态", "客户端IP", "时间"]
    ws.append(headers)
    for it in items:
        ws.append(
            [
                it.get("id"),
                it.get("user_id"),
                it.get("action_type"),
                it.get("sql_text"),
                it.get("operation_type"),
                it.get("datasource_id"),
                it.get("status"),
                it.get("client_ip"),
                it.get("created_at"),
            ]
        )
    buf = io.BytesIO()
    wb.save(buf)
    return buf.getvalue()


async def export_logs(db: AsyncSession, action_type: str = "", status: str = "", fmt: str = "csv") -> tuple[bytes, str]:
    fmt = (fmt or "csv").lower()
    if fmt not in ("csv", "xlsx"):
        raise HTTPException(status_code=400, detail="不支持的导出格式")
    items = await _query_rows(db, action_type, status)
    if fmt == "csv":
        return export_audit_csv(items), "audit_logs.csv"
    return export_audit_excel(items), "audit_logs.xlsx"


async def cleanup_old_logs(db: AsyncSession, days: int = 180) -> int:
    """删除超过保留天数的审计日志，返回删除条数。"""
    if not days or days <= 0:
        return 0
    cutoff = datetime.now() - timedelta(days=days)
    result = await db.execute(delete(AuditLog).where(AuditLog.created_at < cutoff))
    await db.commit()
    return result.rowcount or 0
