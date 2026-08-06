"""元数据服务：对象树、表结构、DDL、收藏。"""
from fastapi import HTTPException
from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from ..adapters import AdapterError
from ..models import FavoritedTable
from .sql_service import build_adapter, get_datasource


async def get_schemas(db: AsyncSession, ds_id: int) -> list[str]:
    ds = await get_datasource(db, ds_id)
    try:
        return build_adapter(ds).get_schemas()
    except AdapterError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


async def get_tables(db: AsyncSession, ds_id: int, schema: str = "") -> list[str]:
    ds = await get_datasource(db, ds_id)
    try:
        return build_adapter(ds).get_tables(schema)
    except AdapterError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


async def get_table_columns(db: AsyncSession, ds_id: int, table: str, schema: str = "") -> list[dict]:
    ds = await get_datasource(db, ds_id)
    try:
        return build_adapter(ds).get_table_columns(table, schema)
    except AdapterError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


async def get_table_indexes(db: AsyncSession, ds_id: int, table: str, schema: str = "") -> list[dict]:
    ds = await get_datasource(db, ds_id)
    try:
        return build_adapter(ds).get_table_indexes(table, schema)
    except AdapterError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


async def get_table_ddl(db: AsyncSession, ds_id: int, table: str, schema: str = "") -> str:
    ds = await get_datasource(db, ds_id)
    try:
        return build_adapter(ds).get_table_ddl(table, schema)
    except AdapterError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


async def get_table_data(db: AsyncSession, ds_id: int, table: str, schema: str = "", page: int = 1, size: int = 100) -> dict:
    ds = await get_datasource(db, ds_id)
    try:
        return build_adapter(ds).get_table_data(table, schema, page, size)
    except AdapterError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


async def get_object_list(db: AsyncSession, ds_id: int, kind: str, schema: str = "") -> list:
    ds = await get_datasource(db, ds_id)
    adapter = build_adapter(ds)
    try:
        if kind == "views":
            return adapter.get_views(schema)
        if kind == "functions":
            return adapter.get_functions(schema)
        if kind == "procedures":
            return adapter.get_procedures(schema)
        if kind == "triggers":
            return adapter.get_triggers(schema)
        if kind == "sequences":
            return adapter.get_sequences(schema)
        raise HTTPException(status_code=400, detail=f"未知对象类型: {kind}")
    except AdapterError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


async def get_object_ddl(db: AsyncSession, ds_id: int, kind: str, name: str, schema: str = "") -> str:
    ds = await get_datasource(db, ds_id)
    adapter = build_adapter(ds)
    try:
        if kind == "views":
            return adapter.get_view_ddl(name, schema)
        if kind == "triggers":
            return adapter.get_trigger_ddl(name, schema)
        raise HTTPException(status_code=400, detail=f"暂不支持该对象类型: {kind}")
    except AdapterError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


async def add_favorite(db: AsyncSession, ds_id: int, schema_name: str, table_name: str) -> dict:
    exists = (
        await db.execute(
            select(FavoritedTable).where(
                FavoritedTable.datasource_id == ds_id,
                FavoritedTable.table_name == table_name,
            )
        )
    ).scalar_one_or_none()
    if exists is None:
        db.add(FavoritedTable(datasource_id=ds_id, schema_name=schema_name, table_name=table_name))
        await db.commit()
    return {"favorited": True}


async def remove_favorite(db: AsyncSession, ds_id: int, table_name: str) -> dict:
    await db.execute(
        delete(FavoritedTable).where(
            FavoritedTable.datasource_id == ds_id,
            FavoritedTable.table_name == table_name,
        )
    )
    await db.commit()
    return {"favorited": False}


async def list_favorites(db: AsyncSession, ds_id: int) -> list[dict]:
    rows = (
        await db.execute(
            select(FavoritedTable).where(FavoritedTable.datasource_id == ds_id).order_by(FavoritedTable.created_at.desc())
        )
    ).scalars().all()
    return [
        {"id": r.id, "schema_name": r.schema_name, "table_name": r.table_name, "created_at": r.created_at.isoformat() if r.created_at else None}
        for r in rows
    ]
