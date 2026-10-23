"""审计日志：统一写入入口、导出与保留策略清理。"""
import csv
import io
import logging
from datetime import datetime, timedelta

from fastapi import HTTPException
from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from ..models import AuditLog

logger = logging.getLogger(__name__)

# 审计失败策略：
#   False（默认）= 尽力而为 —— 审计落库失败只告警，不让已经成功的业务操作变成 500；
#   True         = 审计优先 —— 审计失败即抛出，适用于「无审计不得操作」的合规场景。
AUDIT_FAIL_CLOSED = False


async def record_audit(
    db: AsyncSession,
    user_id: int | None,
    action_type: str,
    sql_text: str,
    operation_type: str,
    datasource_id: int | None,
    status: str,
    client_ip: str = "",
) -> None:
    """写入一条审计日志（SQL 执行、Agent 动作、登录、用户/角色管理、导出等的统一入口）。

    所有审计写入都必须经过本函数：字段口径（``sql_text`` 截断长度、``operation_type``
    语义）只在这里维护一份，新增列时不必逐个调用点修改。
    """
    db.add(
        AuditLog(
            user_id=user_id,
            action_type=action_type,
            sql_text=(sql_text or "")[:4000],
            operation_type=operation_type,
            datasource_id=datasource_id,
            status=status,
            client_ip=client_ip,
        )
    )
    try:
        await db.commit()
    except Exception:  # noqa: BLE001
        logger.warning(
            "审计日志写入失败（action_type=%s operation_type=%s status=%s）",
            action_type,
            operation_type,
            status,
            exc_info=True,
        )
        if AUDIT_FAIL_CLOSED:
            raise
        # 回滚失败的事务，避免会话停留在不可用状态影响后续操作
        try:
            await db.rollback()
        except Exception:  # noqa: BLE001
            logger.warning("审计写入失败后回滚会话也失败", exc_info=True)


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
