"""审计日志路由。"""
from fastapi import APIRouter, Depends, Query
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ..database import get_db
from ..deps import get_current_user
from ..models import AuditLog, User
from ..response import ok, page_data

router = APIRouter(prefix="/api/audit", tags=["审计日志"])


@router.get("/logs")
async def audit_logs(
    action_type: str = "",
    status: str = "",
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    query = select(AuditLog).order_by(AuditLog.id.desc())
    if action_type:
        query = query.where(AuditLog.action_type == action_type)
    if status:
        query = query.where(AuditLog.status == status)
    total = len((await db.execute(query)).scalars().all())
    rows = (await db.execute(query.offset((page - 1) * page_size).limit(page_size))).scalars().all()
    items = [
        {
            "id": r.id,
            "user_id": r.user_id,
            "action_type": r.action_type,
            "sql_text": r.sql_text,
            "operation_type": r.operation_type,
            "datasource_id": r.datasource_id,
            "status": r.status,
            "client_ip": r.client_ip,
            "created_at": r.created_at.isoformat() if r.created_at else None,
        }
        for r in rows
    ]
    return ok(page_data(items, total, page, page_size))
