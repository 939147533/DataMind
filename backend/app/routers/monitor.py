"""运维监控路由：慢查询、连接概览、表结构对比。"""
from datetime import datetime

from fastapi import APIRouter, Depends, Query
from sqlalchemy import case, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from ..database import get_db
from ..models import DataSource, QueryHistory, User
from ..permissions import require_permission
from ..response import ok, page_data
from ..schemas import SchemaCompareRequest
from ..services import metadata_service

router = APIRouter(prefix="/api/monitor", tags=["运维监控"])


@router.get("/overview")
async def overview(
    db: AsyncSession = Depends(get_db),
    user: User = Depends(require_permission("monitor")),
):
    rows = (
        await db.execute(
            select(
                QueryHistory.datasource_id,
                func.count(QueryHistory.id),
                func.avg(QueryHistory.duration_ms),
                func.max(QueryHistory.duration_ms),
                func.sum(case((QueryHistory.status == "success", 1), else_=0)),
            ).group_by(QueryHistory.datasource_id)
        )
    ).all()
    ds_rows = (await db.execute(select(DataSource))).scalars().all()
    ds_map = {d.id: d for d in ds_rows}
    last_rows = (
        await db.execute(
            select(QueryHistory.datasource_id, func.max(QueryHistory.created_at)).group_by(QueryHistory.datasource_id)
        )
    ).all()
    last_map = {r[0]: r[1] for r in last_rows}
    total = (await db.execute(select(func.count(QueryHistory.id)))).scalar_one()
    today = datetime.now().date()
    today_count = (
        await db.execute(
            select(func.count(QueryHistory.id)).where(func.date(QueryHistory.created_at) == today)
        )
    ).scalar_one()
    items = []
    for row in rows:
        ds_id, cnt, avg_dur, max_dur, success_cnt = row
        ds = ds_map.get(ds_id)
        last_ts = last_map.get(ds_id)
        items.append(
            {
                "datasource_id": ds_id,
                "name": ds.name if ds else f"数据源#{ds_id}",
                "db_type": ds.db_type if ds else "",
                "query_count": cnt,
                "avg_duration_ms": round(avg_dur or 0, 1),
                "max_duration_ms": max_dur or 0,
                "success_count": success_cnt or 0,
                "success_rate": round((success_cnt or 0) / cnt * 100, 1) if cnt else 0.0,
                "last_executed_at": last_ts.isoformat() if last_ts else None,
            }
        )
    return ok(
        {
            "total_queries": total,
            "today_queries": today_count,
            "datasources": items,
        }
    )


@router.get("/slow-queries")
async def slow_queries(
    threshold_ms: int = Query(1000, ge=1),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
    user: User = Depends(require_permission("monitor")),
):
    base = select(QueryHistory).where(QueryHistory.duration_ms >= threshold_ms)
    total = (
        await db.execute(select(func.count(QueryHistory.id)).where(QueryHistory.duration_ms >= threshold_ms))
    ).scalar_one()
    rows = (
        await db.execute(base.order_by(QueryHistory.duration_ms.desc()).offset((page - 1) * page_size).limit(page_size))
    ).scalars().all()
    ds_rows = (await db.execute(select(DataSource))).scalars().all()
    ds_map = {d.id: d.name for d in ds_rows}
    items = [
        {
            "id": r.id,
            "datasource_id": r.datasource_id,
            "datasource_name": ds_map.get(r.datasource_id, ""),
            "sql_text": r.sql_text,
            "duration_ms": r.duration_ms,
            "row_count": r.row_count,
            "status": r.status,
            "error_message": r.error_message,
            "created_at": r.created_at.isoformat() if r.created_at else None,
        }
        for r in rows
    ]
    return ok(page_data(items, total, page, page_size))


@router.post("/schema-diff")
async def schema_diff(
    data: SchemaCompareRequest,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(require_permission("monitor")),
):
    return ok(await metadata_service.compare_schemas(db, data.source_ds_id, data.target_ds_id, data.schema_name))
