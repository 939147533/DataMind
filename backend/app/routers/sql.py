"""SQL 工作台路由。"""
from fastapi import APIRouter, Depends, Query, Request
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ..database import get_db
from ..deps import get_client_ip, get_current_user
from ..models import QueryHistory, User
from ..permissions import require_permission
from ..response import ok, page_data
from ..schemas import SqlConfirmRequest, SqlExecuteRequest, SqlFormatRequest
from ..services import sql_service

router = APIRouter(prefix="/api/sql", tags=["SQL 工作台"])


@router.post("/execute")
async def execute(data: SqlExecuteRequest, request: Request, db: AsyncSession = Depends(get_db), user: User = Depends(get_current_user)):
    ds = await sql_service.get_datasource(db, data.datasource_id)
    result = await sql_service.execute_sql(db, ds, data.sql, user.id, get_client_ip(request))
    return ok(result)


@router.post("/execute/confirm")
async def confirm(data: SqlConfirmRequest, request: Request, db: AsyncSession = Depends(get_db), user: User = Depends(get_current_user)):
    result = await sql_service.confirm_execution(db, data.execution_id, data.confirmed, get_client_ip(request))
    return ok(result)


@router.post("/format")
async def format_sql(data: SqlFormatRequest, db: AsyncSession = Depends(get_db), user: User = Depends(require_permission("workspace"))):
    return ok({"sql": sql_service.format_sql(data.sql)})


@router.get("/history")
async def history(
    datasource_id: int | None = None,
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
    user: User = Depends(require_permission("workspace")),
):
    query = select(QueryHistory).order_by(QueryHistory.id.desc())
    if datasource_id:
        query = query.where(QueryHistory.datasource_id == datasource_id)
    total = len((await db.execute(query)).scalars().all())
    rows = (await db.execute(query.offset((page - 1) * page_size).limit(page_size))).scalars().all()
    items = [
        {
            "id": r.id,
            "datasource_id": r.datasource_id,
            "sql_text": r.sql_text,
            "status": r.status,
            "row_count": r.row_count,
            "duration_ms": r.duration_ms,
            "error_message": r.error_message,
            "created_at": r.created_at.isoformat() if r.created_at else None,
        }
        for r in rows
    ]
    return ok(page_data(items, total, page, page_size))
