"""可视化报表路由：图表与仪表盘。"""
import json
import secrets

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ..database import get_db
from ..models import Chart, Dashboard, User
from ..permissions import require_any_permission, require_permission
from ..response import ok
from ..schemas import ChartCreate, ChartUpdate, DashboardCreate, DashboardUpdate
from ..services.export_service import _run_query
from ..services.sql_service import get_datasource

router = APIRouter(prefix="/api", tags=["可视化报表"])


def _chart_out(c: Chart) -> dict:
    return {
        "id": c.id,
        "name": c.name,
        "datasource_id": c.datasource_id,
        "sql_text": c.sql_text,
        "chart_type": c.chart_type,
        "x_column": c.x_column,
        "y_column": c.y_column,
        "aggregation": c.aggregation,
        "options": c.options,
        "created_at": c.created_at.isoformat() if c.created_at else None,
    }


def _dashboard_out(d: Dashboard) -> dict:
    try:
        chart_ids = json.loads(d.chart_ids or "[]")
    except Exception:  # noqa: BLE001
        chart_ids = []
    return {
        "id": d.id,
        "name": d.name,
        "chart_ids": chart_ids,
        "layout": d.layout,
        "is_public": d.is_public,
        "share_token": d.share_token,
        "created_at": d.created_at.isoformat() if d.created_at else None,
    }


# ---------- 图表 ----------
@router.post("/charts")
async def create_chart(data: ChartCreate, db: AsyncSession = Depends(get_db), user: User = Depends(require_permission("reports_manage"))):
    chart = Chart(**data.model_dump())
    db.add(chart)
    await db.commit()
    await db.refresh(chart)
    return ok(_chart_out(chart), "创建成功")


@router.get("/charts")
async def list_charts(db: AsyncSession = Depends(get_db), user: User = Depends(require_any_permission("reports", "reports_manage"))):
    rows = (await db.execute(select(Chart).order_by(Chart.id.desc()))).scalars().all()
    return ok([_chart_out(c) for c in rows])


@router.put("/charts/{chart_id}")
async def update_chart(chart_id: int, data: ChartUpdate, db: AsyncSession = Depends(get_db), user: User = Depends(require_permission("reports_manage"))):
    chart = (await db.execute(select(Chart).where(Chart.id == chart_id))).scalar_one_or_none()
    if chart is None:
        raise HTTPException(status_code=404, detail="图表不存在")
    for field, value in data.model_dump(exclude_unset=True).items():
        setattr(chart, field, value)
    await db.commit()
    await db.refresh(chart)
    return ok(_chart_out(chart), "更新成功")


@router.delete("/charts/{chart_id}")
async def delete_chart(chart_id: int, db: AsyncSession = Depends(get_db), user: User = Depends(require_permission("reports_manage"))):
    chart = (await db.execute(select(Chart).where(Chart.id == chart_id))).scalar_one_or_none()
    if chart is None:
        raise HTTPException(status_code=404, detail="图表不存在")
    await db.delete(chart)
    await db.commit()
    return ok(message="删除成功")


@router.get("/charts/{chart_id}/data")
async def chart_data(chart_id: int, db: AsyncSession = Depends(get_db), user: User = Depends(require_any_permission("reports", "reports_manage"))):
    chart = (await db.execute(select(Chart).where(Chart.id == chart_id))).scalar_one_or_none()
    if chart is None:
        raise HTTPException(status_code=404, detail="图表不存在")
    if not chart.datasource_id:
        raise HTTPException(status_code=400, detail="图表未关联数据源")
    ds = await get_datasource(db, chart.datasource_id)
    columns, rows = _run_query(ds, chart.sql_text)
    return ok({"columns": columns, "rows": rows})


# ---------- 仪表盘 ----------
@router.post("/dashboards")
async def create_dashboard(data: DashboardCreate, db: AsyncSession = Depends(get_db), user: User = Depends(require_permission("reports_manage"))):
    dashboard = Dashboard(name=data.name, chart_ids=json.dumps(data.chart_ids), layout=data.layout)
    db.add(dashboard)
    await db.commit()
    await db.refresh(dashboard)
    return ok(_dashboard_out(dashboard), "创建成功")


@router.get("/dashboards")
async def list_dashboards(db: AsyncSession = Depends(get_db), user: User = Depends(require_any_permission("reports", "reports_manage"))):
    rows = (await db.execute(select(Dashboard).order_by(Dashboard.id.desc()))).scalars().all()
    return ok([_dashboard_out(d) for d in rows])


@router.put("/dashboards/{dashboard_id}")
async def update_dashboard(dashboard_id: int, data: DashboardUpdate, db: AsyncSession = Depends(get_db), user: User = Depends(require_permission("reports_manage"))):
    dashboard = (await db.execute(select(Dashboard).where(Dashboard.id == dashboard_id))).scalar_one_or_none()
    if dashboard is None:
        raise HTTPException(status_code=404, detail="仪表盘不存在")
    payload = data.model_dump(exclude_unset=True)
    if "chart_ids" in payload and payload["chart_ids"] is not None:
        dashboard.chart_ids = json.dumps(payload["chart_ids"])
        payload.pop("chart_ids")
    if "name" in payload:
        dashboard.name = payload.pop("name")
    if "layout" in payload:
        dashboard.layout = payload.pop("layout")
    if "is_public" in payload:
        dashboard.is_public = payload.pop("is_public")
    await db.commit()
    await db.refresh(dashboard)
    return ok(_dashboard_out(dashboard), "更新成功")


@router.delete("/dashboards/{dashboard_id}")
async def delete_dashboard(dashboard_id: int, db: AsyncSession = Depends(get_db), user: User = Depends(require_permission("reports_manage"))):
    dashboard = (await db.execute(select(Dashboard).where(Dashboard.id == dashboard_id))).scalar_one_or_none()
    if dashboard is None:
        raise HTTPException(status_code=404, detail="仪表盘不存在")
    await db.delete(dashboard)
    await db.commit()
    return ok(message="删除成功")


@router.post("/dashboards/{dashboard_id}/share")
async def share_dashboard(dashboard_id: int, db: AsyncSession = Depends(get_db), user: User = Depends(require_permission("reports_manage"))):
    dashboard = (await db.execute(select(Dashboard).where(Dashboard.id == dashboard_id))).scalar_one_or_none()
    if dashboard is None:
        raise HTTPException(status_code=404, detail="仪表盘不存在")
    dashboard.is_public = True
    dashboard.share_token = secrets.token_urlsafe(16)
    await db.commit()
    return ok({"share_token": dashboard.share_token, "share_url": f"/share/{dashboard.share_token}"})


@router.get("/share/{token}")
async def share_view(token: str, db: AsyncSession = Depends(get_db)):
    dashboard = (await db.execute(select(Dashboard).where(Dashboard.share_token == token, Dashboard.is_public.is_(True)))).scalar_one_or_none()
    if dashboard is None:
        raise HTTPException(status_code=404, detail="分享不存在或已关闭")
    return ok(_dashboard_out(dashboard))
