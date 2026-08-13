"""定时导出路由。"""
from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import FileResponse
from sqlalchemy.ext.asyncio import AsyncSession

from ..config import EXPORTS_DIR
from ..database import get_db
from ..models import User
from ..permissions import require_permission
from ..response import ok
from ..schemas import ScheduleCreate, ScheduleUpdate
from ..services import schedule_service

router = APIRouter(prefix="/api/schedule", tags=["定时导出"])


@router.get("")
async def list_schedules(
    db: AsyncSession = Depends(get_db),
    user: User = Depends(require_permission("reports_manage")),
):
    return ok(await schedule_service.list_schedules(db))


@router.post("")
async def create_schedule(
    data: ScheduleCreate,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(require_permission("reports_manage")),
):
    task = await schedule_service.create_schedule(db, data)
    return ok(schedule_service._out(task), "创建成功")


@router.put("/{schedule_id}")
async def update_schedule(
    schedule_id: int,
    data: ScheduleUpdate,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(require_permission("reports_manage")),
):
    task = await schedule_service.update_schedule(db, schedule_id, data)
    return ok(schedule_service._out(task), "已更新")


@router.delete("/{schedule_id}")
async def delete_schedule(
    schedule_id: int,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(require_permission("reports_manage")),
):
    await schedule_service.delete_schedule(db, schedule_id)
    return ok(message="已删除")


@router.post("/{schedule_id}/run")
async def run_schedule(
    schedule_id: int,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(require_permission("reports_manage")),
):
    result = await schedule_service.run_schedule(db, schedule_id)
    return ok(result, result.get("message", "执行完成"))


@router.get("/{schedule_id}/file")
async def download_schedule_file(
    schedule_id: int,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(require_permission("reports_manage")),
):
    task = await schedule_service.get_schedule(db, schedule_id)
    if not task.last_file:
        raise HTTPException(status_code=404, detail="尚无导出文件")
    path = EXPORTS_DIR / task.last_file
    if not path.exists():
        raise HTTPException(status_code=404, detail="导出文件不存在")
    return FileResponse(path, filename=path.name, media_type="application/octet-stream")
