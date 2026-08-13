"""SQL 收藏/模板路由。"""
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from ..database import get_db
from ..models import SavedQuery, User
from ..permissions import require_any_permission
from ..response import ok, page_data
from ..schemas import SavedQueryCreate, SavedQueryUpdate

router = APIRouter(prefix="/api/saved-queries", tags=["SQL 收藏"])


def _out(q: SavedQuery) -> dict:
    return {
        "id": q.id,
        "name": q.name,
        "sql_text": q.sql_text,
        "datasource_id": q.datasource_id,
        "description": q.description,
        "created_at": q.created_at.isoformat() if q.created_at else None,
        "updated_at": q.updated_at.isoformat() if q.updated_at else None,
    }


@router.get("")
async def list_saved(
    search: str = "",
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
    user: User = Depends(require_any_permission("workspace", "ai_query")),
):
    query = select(SavedQuery)
    if search:
        query = query.where(or_(SavedQuery.name.contains(search), SavedQuery.sql_text.contains(search)))
    total = (await db.execute(query)).scalars().all()
    rows = (await db.execute(query.order_by(SavedQuery.id.desc()).offset((page - 1) * page_size).limit(page_size))).scalars().all()
    return ok(page_data([_out(r) for r in rows], len(total), page, page_size))


@router.post("")
async def create_saved(
    data: SavedQueryCreate,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(require_any_permission("workspace", "ai_query")),
):
    if not data.name.strip():
        raise HTTPException(status_code=400, detail="名称不能为空")
    q = SavedQuery(name=data.name.strip(), sql_text=data.sql_text, datasource_id=data.datasource_id, description=data.description)
    db.add(q)
    await db.commit()
    await db.refresh(q)
    return ok(_out(q), "已收藏")


@router.put("/{query_id}")
async def update_saved(
    query_id: int,
    data: SavedQueryUpdate,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(require_any_permission("workspace", "ai_query")),
):
    q = (await db.execute(select(SavedQuery).where(SavedQuery.id == query_id))).scalar_one_or_none()
    if q is None:
        raise HTTPException(status_code=404, detail="收藏不存在")
    for field, value in data.model_dump(exclude_unset=True).items():
        setattr(q, field, value)
    await db.commit()
    await db.refresh(q)
    return ok(_out(q), "已更新")


@router.delete("/{query_id}")
async def delete_saved(
    query_id: int,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(require_any_permission("workspace", "ai_query")),
):
    q = (await db.execute(select(SavedQuery).where(SavedQuery.id == query_id))).scalar_one_or_none()
    if q is None:
        raise HTTPException(status_code=404, detail="收藏不存在")
    await db.delete(q)
    await db.commit()
    return ok(message="已删除")
