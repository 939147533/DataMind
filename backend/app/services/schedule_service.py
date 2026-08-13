"""定时导出服务：任务调度与执行。"""
import asyncio
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ..config import EXPORTS_DIR
from ..models import ScheduledExport
from .export_service import export_result_file
from .sql_service import get_datasource


def _next_run(task: ScheduledExport) -> datetime:
    return datetime.now() + timedelta(minutes=max(1, task.interval_minutes or 1440))


def _out(t: ScheduledExport) -> dict:
    return {
        "id": t.id,
        "name": t.name,
        "datasource_id": t.datasource_id,
        "sql_text": t.sql_text,
        "format": t.format,
        "interval_minutes": t.interval_minutes,
        "enabled": t.enabled,
        "last_run_at": t.last_run_at.isoformat() if t.last_run_at else None,
        "last_status": t.last_status,
        "last_file": t.last_file,
        "next_run_at": t.next_run_at.isoformat() if t.next_run_at else None,
        "created_at": t.created_at.isoformat() if t.created_at else None,
        "updated_at": t.updated_at.isoformat() if t.updated_at else None,
    }


async def get_schedule(db: AsyncSession, schedule_id: int) -> ScheduledExport:
    task = (await db.execute(select(ScheduledExport).where(ScheduledExport.id == schedule_id))).scalar_one_or_none()
    if task is None:
        raise HTTPException(status_code=404, detail="定时任务不存在")
    return task


async def list_schedules(db: AsyncSession) -> list[dict]:
    rows = (await db.execute(select(ScheduledExport).order_by(ScheduledExport.id.desc()))).scalars().all()
    return [_out(t) for t in rows]


async def create_schedule(db: AsyncSession, data) -> ScheduledExport:
    if not data.name.strip():
        raise HTTPException(status_code=400, detail="名称不能为空")
    if not data.sql_text.strip():
        raise HTTPException(status_code=400, detail="SQL 不能为空")
    task = ScheduledExport(
        name=data.name.strip(),
        datasource_id=data.datasource_id,
        sql_text=data.sql_text,
        format=data.format or "csv",
        interval_minutes=data.interval_minutes or 1440,
        enabled=data.enabled,
        next_run_at=datetime.now() + timedelta(minutes=max(1, data.interval_minutes or 1440)),
    )
    db.add(task)
    await db.commit()
    await db.refresh(task)
    return task


async def update_schedule(db: AsyncSession, schedule_id: int, data) -> ScheduledExport:
    task = await get_schedule(db, schedule_id)
    for field, value in data.model_dump(exclude_unset=True).items():
        setattr(task, field, value)
    if "interval_minutes" in data.model_dump(exclude_unset=True) and data.interval_minutes:
        task.next_run_at = datetime.now() + timedelta(minutes=max(1, data.interval_minutes))
    await db.commit()
    await db.refresh(task)
    return task


async def delete_schedule(db: AsyncSession, schedule_id: int) -> None:
    task = await get_schedule(db, schedule_id)
    await db.delete(task)
    await db.commit()


async def run_schedule(db: AsyncSession, schedule_id: int) -> dict:
    task = await get_schedule(db, schedule_id)
    ds = await get_datasource(db, task.datasource_id)
    loop = asyncio.get_running_loop()
    with ThreadPoolExecutor(max_workers=1) as pool:
        content, filename = await loop.run_in_executor(pool, export_result_file, ds, task.sql_text, task.format, task.name[:31] or "结果")
    EXPORTS_DIR.mkdir(parents=True, exist_ok=True)
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    target = EXPORTS_DIR / f"schedule_{task.id}_{ts}_{filename}"
    target.write_bytes(content)
    task.last_run_at = datetime.now()
    task.last_status = "success"
    task.last_file = target.name
    task.next_run_at = _next_run(task)
    await db.commit()
    return {"task_id": task.id, "file": target.name, "message": "导出完成"}


async def run_schedule_safe(db: AsyncSession, schedule_id: int) -> None:
    """失败不抛出，仅记录状态并顺延下次执行。"""
    try:
        await run_schedule(db, schedule_id)
    except Exception as exc:  # noqa: BLE001
        try:
            task = await get_schedule(db, schedule_id)
            task.last_status = f"failed: {str(exc)[:200]}"
            task.next_run_at = _next_run(task)
            await db.commit()
        except Exception:  # noqa: BLE001
            pass


async def scheduler_loop() -> None:
    """后台循环：每分钟检查到期的定时任务。"""
    from ..database import SessionLocal

    while True:
        try:
            async with SessionLocal() as db:
                now = datetime.now()
                rows = (
                    await db.execute(
                        select(ScheduledExport).where(
                            ScheduledExport.enabled.is_(True),
                            ScheduledExport.next_run_at.isnot(None),
                            ScheduledExport.next_run_at <= now,
                        )
                    )
                ).scalars().all()
                for task in rows:
                    await run_schedule_safe(db, task.id)
        except Exception:  # noqa: BLE001
            pass
        await asyncio.sleep(60)
