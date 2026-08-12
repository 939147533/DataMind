"""文档导出路由。"""
from fastapi import APIRouter, Depends, Query
from fastapi.responses import FileResponse, Response
from sqlalchemy.ext.asyncio import AsyncSession

from ..database import get_db
from ..models import User
from ..permissions import require_any_permission
from ..response import ok
from ..schemas import ExportDatabaseRequest, ExportResultRequest
from ..services import export_service
from ..services.sql_service import get_datasource

router = APIRouter(prefix="/api/export", tags=["文档导出"])


@router.post("/result")
async def export_result(
    data: ExportResultRequest,
    format: str = Query("csv"),
    db: AsyncSession = Depends(get_db),
    user: User = Depends(require_any_permission("workspace", "reports")),
):
    ds = await get_datasource(db, data.datasource_id)
    content, filename = export_service.export_result_file(ds, data.sql, format, data.sheet_name)
    return Response(
        content=content,
        media_type="application/octet-stream",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@router.post("/database")
async def export_database(
    data: ExportDatabaseRequest,
    format: str = Query("word"),
    db: AsyncSession = Depends(get_db),
    user: User = Depends(require_any_permission("workspace", "reports")),
):
    ds = await get_datasource(db, data.datasource_id)
    task_id = export_service.start_database_export(ds, data.tables, format, data.include_ddl)
    return ok({"task_id": task_id, "status": "running"})


@router.get("/database/status/{task_id}")
async def export_status(task_id: str, db: AsyncSession = Depends(get_db), user: User = Depends(require_any_permission("workspace", "reports"))):
    return ok(export_service.get_task_status(task_id))


@router.get("/database/download/{task_id}")
async def export_download(task_id: str, db: AsyncSession = Depends(get_db), user: User = Depends(require_any_permission("workspace", "reports"))):
    path = export_service.get_task_file(task_id)
    return FileResponse(path, filename=path.name, media_type="application/octet-stream")
