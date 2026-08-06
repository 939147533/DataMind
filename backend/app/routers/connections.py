"""连接管理路由。"""
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession

from ..adapters import AdapterError
from ..database import get_db
from ..deps import get_current_user
from ..models import User
from ..response import ok, page_data
from ..schemas import ConnectionCreate, ConnectionUpdate, TestConnectionRequest
from ..services import connection_service as service

router = APIRouter(prefix="/api/connections", tags=["连接管理"])


@router.post("/test")
async def test_connection(data: TestConnectionRequest, user: User = Depends(get_current_user)):
    try:
        ok_flag, message = service.test_connection_params(data)
    except AdapterError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return ok({"success": ok_flag, "message": message}, message)


@router.post("")
async def create_connection(data: ConnectionCreate, db: AsyncSession = Depends(get_db), user: User = Depends(get_current_user)):
    ds = await service.create_connection(db, data)
    return ok(service.to_out(ds), "创建成功")


@router.get("")
async def list_connections(
    search: str = "",
    environment: str = "",
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    result = await service.list_connections(db, search, environment, page, page_size)
    return ok(page_data(result["list"], result["total"], page, page_size))


@router.get("/{connection_id}")
async def get_connection(connection_id: int, db: AsyncSession = Depends(get_db), user: User = Depends(get_current_user)):
    ds = await service.get_connection(db, connection_id)
    return ok(service.to_out(ds))


@router.put("/{connection_id}")
async def update_connection(connection_id: int, data: ConnectionUpdate, db: AsyncSession = Depends(get_db), user: User = Depends(get_current_user)):
    ds = await service.update_connection(db, connection_id, data)
    return ok(service.to_out(ds), "更新成功")


@router.delete("/{connection_id}")
async def delete_connection(connection_id: int, db: AsyncSession = Depends(get_db), user: User = Depends(get_current_user)):
    await service.delete_connection(db, connection_id)
    return ok(message="删除成功")


@router.post("/{connection_id}/clone")
async def clone_connection(connection_id: int, db: AsyncSession = Depends(get_db), user: User = Depends(get_current_user)):
    ds = await service.clone_connection(db, connection_id)
    return ok(service.to_out(ds), "克隆成功")


@router.post("/{connection_id}/connect")
async def connect(connection_id: int, db: AsyncSession = Depends(get_db), user: User = Depends(get_current_user)):
    ok_flag, message = await service.test_saved_connection(db, connection_id)
    if not ok_flag:
        raise HTTPException(status_code=400, detail=message)
    from ..services.metadata_service import get_schemas

    schemas = await get_schemas(db, connection_id)
    return ok({"status": "active", "schemas": schemas}, "连接成功")
