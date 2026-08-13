"""元数据服务：对象树、表结构、DDL、收藏。"""
from fastapi import HTTPException
from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from ..adapters import AdapterError
from ..models import DataSource, FavoritedTable
from .sql_service import build_adapter, execute_sql, get_datasource


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
        if kind == "functions":
            return adapter.get_function_ddl(name, schema)
        if kind == "procedures":
            return adapter.get_procedure_ddl(name, schema)
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


# ---------- 表数据编辑（构造 DML 并复用 SQL 安全执行协议） ----------
def _qualified_table(table: str, schema: str, db_type: str) -> str:
    from .sql_service import quote_identifier

    t = quote_identifier(table, db_type)
    return f"{quote_identifier(schema, db_type)}.{t}" if schema and schema.strip() else t


def build_update_sql(ds: DataSource, table: str, schema: str, set_values: dict, where: dict) -> str:
    from .sql_service import quote_identifier, quote_value

    if not set_values or not where:
        raise HTTPException(status_code=400, detail="更新操作需要 set_values 与 where 条件")
    db_type = ds.db_type
    sets = ", ".join(f"{quote_identifier(k, db_type)} = {quote_value(v)}" for k, v in set_values.items())
    conds = " AND ".join(f"{quote_identifier(k, db_type)} = {quote_value(v)}" for k, v in where.items())
    return f"UPDATE {_qualified_table(table, schema, db_type)} SET {sets} WHERE {conds}"


def build_insert_sql(ds: DataSource, table: str, schema: str, values: dict) -> str:
    from .sql_service import quote_identifier, quote_value

    if not values:
        raise HTTPException(status_code=400, detail="插入操作需要 values")
    db_type = ds.db_type
    cols = ", ".join(quote_identifier(k, db_type) for k in values.keys())
    vals = ", ".join(quote_value(v) for v in values.values())
    return f"INSERT INTO {_qualified_table(table, schema, db_type)} ({cols}) VALUES ({vals})"


def build_delete_sql(ds: DataSource, table: str, schema: str, where: dict) -> str:
    from .sql_service import quote_identifier, quote_value

    if not where:
        raise HTTPException(status_code=400, detail="删除操作需要 where 条件（禁止全表删除）")
    db_type = ds.db_type
    conds = " AND ".join(f"{quote_identifier(k, db_type)} = {quote_value(v)}" for k, v in where.items())
    return f"DELETE FROM {_qualified_table(table, schema, db_type)} WHERE {conds}"


async def update_table_row(db: AsyncSession, ds_id: int, table: str, data, user_id: int | None = None) -> dict:
    ds = await get_datasource(db, ds_id)
    sql = build_update_sql(ds, table, data.schema_name, data.set_values, data.where)
    result = await execute_sql(db, ds, sql, user_id, "")
    result["sql_text"] = sql
    return result


async def insert_table_row(db: AsyncSession, ds_id: int, table: str, data, user_id: int | None = None) -> dict:
    ds = await get_datasource(db, ds_id)
    sql = build_insert_sql(ds, table, data.schema_name, data.values)
    result = await execute_sql(db, ds, sql, user_id, "")
    result["sql_text"] = sql
    return result


async def delete_table_row(db: AsyncSession, ds_id: int, table: str, data, user_id: int | None = None) -> dict:
    ds = await get_datasource(db, ds_id)
    sql = build_delete_sql(ds, table, data.schema_name, data.where)
    result = await execute_sql(db, ds, sql, user_id, "")
    result["sql_text"] = sql
    return result


# ---------- 表结构对比 ----------
async def compare_schemas(db: AsyncSession, source_ds_id: int, target_ds_id: int, schema: str = "") -> dict:
    src = await get_datasource(db, source_ds_id)
    tgt = await get_datasource(db, target_ds_id)
    try:
        src_adapter = build_adapter(src)
        tgt_adapter = build_adapter(tgt)
    except AdapterError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    try:
        src_tables = set(src_adapter.get_tables(schema) or [])
        tgt_tables = set(tgt_adapter.get_tables(schema) or [])
        table_diffs = []
        for table in sorted(src_tables & tgt_tables):
            src_cols = {c["name"]: c for c in src_adapter.get_table_columns(table, schema)}
            tgt_cols = {c["name"]: c for c in tgt_adapter.get_table_columns(table, schema)}
            added = sorted(set(tgt_cols) - set(src_cols))
            removed = sorted(set(src_cols) - set(tgt_cols))
            changed = []
            for name in sorted(set(src_cols) & set(tgt_cols)):
                if (src_cols[name].get("data_type") or "") != (tgt_cols[name].get("data_type") or ""):
                    changed.append(
                        {
                            "column": name,
                            "source_type": src_cols[name].get("data_type") or "",
                            "target_type": tgt_cols[name].get("data_type") or "",
                        }
                    )
            if added or removed or changed:
                table_diffs.append({"table": table, "added_columns": added, "removed_columns": removed, "changed_columns": changed})
        return {
            "source_ds_id": source_ds_id,
            "target_ds_id": target_ds_id,
            "schema": schema,
            "only_source": sorted(src_tables - tgt_tables),
            "only_target": sorted(tgt_tables - src_tables),
            "table_diffs": table_diffs,
        }
    except AdapterError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
