"""元数据路由：对象树、表结构、收藏、表结构编辑。"""
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession

from ..database import get_db
from ..models import User
from ..permissions import require_any_permission
from ..response import ok
from ..schemas import AlterTableRequest, FavoriteRequest
from ..services import metadata_service
from ..services.agent_service import resolve_model_config
from ..services.llm_providers import build_messages, get_llm_provider
from ..services.sql_service import execute_sql, get_datasource

router = APIRouter(prefix="/api/metadata", tags=["元数据"])


@router.get("/{ds_id}/schemas")
async def schemas(ds_id: int, db: AsyncSession = Depends(get_db), user: User = Depends(require_any_permission("workspace", "reports"))):
    return ok(await metadata_service.get_schemas(db, ds_id))


@router.get("/{ds_id}/tables")
async def tables(ds_id: int, schema: str = "", db: AsyncSession = Depends(get_db), user: User = Depends(require_any_permission("workspace", "reports"))):
    return ok(await metadata_service.get_tables(db, ds_id, schema))


@router.get("/{ds_id}/tables/{table}/columns")
async def columns(ds_id: int, table: str, schema: str = "", db: AsyncSession = Depends(get_db), user: User = Depends(require_any_permission("workspace", "reports"))):
    return ok(await metadata_service.get_table_columns(db, ds_id, table, schema))


@router.get("/{ds_id}/tables/{table}/indexes")
async def indexes(ds_id: int, table: str, schema: str = "", db: AsyncSession = Depends(get_db), user: User = Depends(require_any_permission("workspace", "reports"))):
    return ok(await metadata_service.get_table_indexes(db, ds_id, table, schema))


@router.get("/{ds_id}/tables/{table}/ddl")
async def table_ddl(ds_id: int, table: str, schema: str = "", db: AsyncSession = Depends(get_db), user: User = Depends(require_any_permission("workspace", "reports"))):
    return ok({"ddl": await metadata_service.get_table_ddl(db, ds_id, table, schema)})


@router.get("/{ds_id}/tables/{table}/data")
async def table_data(
    ds_id: int,
    table: str,
    schema: str = "",
    page: int = Query(1, ge=1),
    size: int = Query(100, ge=1, le=1000),
    db: AsyncSession = Depends(get_db),
    user: User = Depends(require_any_permission("workspace", "reports")),
):
    return ok(await metadata_service.get_table_data(db, ds_id, table, schema, page, size))


@router.post("/{ds_id}/tables/{table}/alter")
async def alter_table(ds_id: int, table: str, data: AlterTableRequest, db: AsyncSession = Depends(get_db), user: User = Depends(require_any_permission("workspace", "reports"))):
    ddl = data.ddl.strip()
    if not ddl and data.changes.strip():
        config = await resolve_model_config(db, None, None)
        if config is None:
            raise HTTPException(status_code=400, detail="未配置 AI 模型，请直接提供 DDL")
        provider = get_llm_provider(config)
        adapter_ddl = ""
        try:
            adapter_ddl = await metadata_service.get_table_ddl(db, ds_id, table, data.schema_name)
        except Exception:  # noqa: BLE001
            adapter_ddl = ""
        prompt = (
            f"当前表 DDL：\n{adapter_ddl}\n"
            f"请根据变更描述生成 ALTER TABLE {table} 的 SQL（仅输出 SQL，不要其他内容）：\n{data.changes}"
        )
        try:
            ddl = (await provider.chat(build_messages("你是数据库 DDL 生成专家。", [], prompt))).strip()
        except Exception as exc:  # noqa: BLE001
            raise HTTPException(status_code=400, detail=f"AI 生成 DDL 失败: {exc}") from exc
        ddl = ddl.strip("`")
        if ddl.lower().startswith("sql"):
            ddl = ddl[3:].strip()
    if not ddl:
        raise HTTPException(status_code=400, detail="缺少 DDL 或变更描述")
    ds = await get_datasource(db, ds_id)
    result = await execute_sql(db, ds, ddl, user.id, "", session_id=None)
    result["generated_ddl"] = ddl
    return ok(result)


# ---------- 收藏（须在通用 /{ds_id}/{kind} 之前声明） ----------
@router.get("/{ds_id}/favorites")
async def favorites(ds_id: int, db: AsyncSession = Depends(get_db), user: User = Depends(require_any_permission("workspace", "reports"))):
    return ok(await metadata_service.list_favorites(db, ds_id))


@router.post("/{ds_id}/favorites")
async def add_favorite(ds_id: int, data: FavoriteRequest, db: AsyncSession = Depends(get_db), user: User = Depends(require_any_permission("workspace", "reports"))):
    return ok(await metadata_service.add_favorite(db, ds_id, data.schema_name, data.table_name))


@router.delete("/{ds_id}/favorites/{table_name}")
async def remove_favorite(ds_id: int, table_name: str, db: AsyncSession = Depends(get_db), user: User = Depends(require_any_permission("workspace", "reports"))):
    return ok(await metadata_service.remove_favorite(db, ds_id, table_name))


# ---------- 视图/函数/存储过程/触发器/序列 ----------
@router.get("/{ds_id}/{kind}")
async def object_list(
    ds_id: int,
    kind: str,
    schema: str = "",
    db: AsyncSession = Depends(get_db),
    user: User = Depends(require_any_permission("workspace", "reports")),
):
    return ok(await metadata_service.get_object_list(db, ds_id, kind, schema))


@router.get("/{ds_id}/{kind}/{name}/ddl")
async def object_ddl(
    ds_id: int,
    kind: str,
    name: str,
    schema: str = "",
    db: AsyncSession = Depends(get_db),
    user: User = Depends(require_any_permission("workspace", "reports")),
):
    return ok({"ddl": await metadata_service.get_object_ddl(db, ds_id, kind, name, schema)})
