"""连接管理服务。"""
from datetime import datetime

from fastapi import HTTPException
from sqlalchemy import or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from pathlib import Path

from ..adapters import test_connection
from ..config import DRIVERS_DIR, normalize_database_name, resolve_data_path, to_data_relative
from ..models import DataSource, JdbcDriver
from ..schemas import ConnectionCreate, ConnectionUpdate, TestConnectionRequest
from ..security import decrypt_text, encrypt_text
from .sql_service import build_connection_info


def to_out(ds: DataSource) -> dict:
    return {
        "id": ds.id,
        "name": ds.name,
        "db_type": ds.db_type,
        "host": ds.host,
        "port": ds.port,
        "username": ds.username,
        "has_password": bool(ds.encrypted_password),
        "database_name": ds.database_name,
        "ssh_enabled": ds.ssh_enabled,
        "ssh_host": ds.ssh_host,
        "ssh_port": ds.ssh_port,
        "ssh_user": ds.ssh_user,
        "ssh_auth_type": ds.ssh_auth_type,
        "environment": ds.environment,
        "status": ds.status,
        "description": ds.description,
        "created_at": ds.created_at.isoformat() if ds.created_at else None,
        "updated_at": ds.updated_at.isoformat() if ds.updated_at else None,
    }


async def create_connection(db: AsyncSession, data: ConnectionCreate) -> DataSource:
    exists = (await db.execute(select(DataSource).where(DataSource.name == data.name))).scalar_one_or_none()
    if exists:
        raise HTTPException(status_code=400, detail="连接名称已存在")
    ds = DataSource(
        name=data.name,
        db_type=data.db_type,
        host=data.host,
        port=data.port,
        username=data.username,
        encrypted_password=encrypt_text(data.password),
        database_name=normalize_database_name(data.db_type, data.database_name),
        ssh_enabled=data.ssh_enabled,
        ssh_host=data.ssh_host,
        ssh_port=data.ssh_port,
        ssh_user=data.ssh_user,
        ssh_auth_type=data.ssh_auth_type,
        ssh_private_key=encrypt_text(data.ssh_private_key),
        environment=data.environment,
        description=data.description,
        status="unknown",
    )
    db.add(ds)
    await db.commit()
    await db.refresh(ds)
    return ds


async def list_connections(db: AsyncSession, search: str = "", environment: str = "", page: int = 1, page_size: int = 20) -> dict:
    query = select(DataSource)
    if search:
        query = query.where(or_(DataSource.name.contains(search), DataSource.host.contains(search)))
    if environment:
        query = query.where(DataSource.environment == environment)
    total = len((await db.execute(query)).scalars().all())
    rows = (await db.execute(query.order_by(DataSource.id.desc()).offset((page - 1) * page_size).limit(page_size))).scalars().all()
    return {
        "list": [to_out(ds) for ds in rows],
        "total": total,
        "page": page,
        "page_size": page_size,
    }


async def get_connection(db: AsyncSession, connection_id: int) -> DataSource:
    ds = (await db.execute(select(DataSource).where(DataSource.id == connection_id))).scalar_one_or_none()
    if ds is None:
        raise HTTPException(status_code=404, detail="连接不存在")
    return ds


async def update_connection(db: AsyncSession, connection_id: int, data: ConnectionUpdate) -> DataSource:
    ds = await get_connection(db, connection_id)
    for field in ("name", "db_type", "host", "port", "username", "database_name", "ssh_enabled", "ssh_host", "ssh_port", "ssh_user", "ssh_auth_type", "environment", "description"):
        setattr(ds, field, getattr(data, field))
    ds.database_name = normalize_database_name(ds.db_type, ds.database_name)
    if data.password:
        ds.encrypted_password = encrypt_text(data.password)
    if data.ssh_private_key:
        ds.ssh_private_key = encrypt_text(data.ssh_private_key)
    ds.updated_at = datetime.now()
    await db.commit()
    await db.refresh(ds)
    return ds


async def delete_connection(db: AsyncSession, connection_id: int) -> None:
    ds = await get_connection(db, connection_id)
    await db.delete(ds)
    await db.commit()


async def repair_stored_paths(db: AsyncSession) -> int:
    """启动时修复历史数据源/驱动路径：指向数据目录的绝对路径统一改写为相对路径（项目改名后自动修复）。"""
    changed = 0
    rows = (await db.execute(select(DataSource).where(DataSource.db_type == "sqlite"))).scalars().all()
    for ds in rows:
        name = (ds.database_name or "").strip()
        if not name or not Path(name).is_absolute():
            continue
        resolved = resolve_data_path(name)
        if not resolved.exists():
            continue
        new_name = to_data_relative(resolved)
        if new_name != name:
            ds.database_name = new_name
            changed += 1
    drivers = (await db.execute(select(JdbcDriver))).scalars().all()
    for drv in drivers:
        fp = (drv.file_path or "").strip()
        if not fp or not Path(fp).is_absolute():
            continue
        resolved = Path(fp) if Path(fp).exists() else DRIVERS_DIR / Path(fp).name
        if not resolved.exists():
            continue
        new_fp = to_data_relative(resolved)
        if new_fp != fp:
            drv.file_path = new_fp
            changed += 1
    if changed:
        await db.commit()
    return changed


async def clone_connection(db: AsyncSession, connection_id: int) -> DataSource:
    ds = await get_connection(db, connection_id)
    new_ds = DataSource(
        name=f"{ds.name} (副本)",
        db_type=ds.db_type,
        host=ds.host,
        port=ds.port,
        username=ds.username,
        encrypted_password=ds.encrypted_password,
        database_name=ds.database_name,
        ssh_enabled=ds.ssh_enabled,
        ssh_host=ds.ssh_host,
        ssh_port=ds.ssh_port,
        ssh_user=ds.ssh_user,
        ssh_auth_type=ds.ssh_auth_type,
        ssh_private_key=ds.ssh_private_key,
        environment=ds.environment,
        description=ds.description,
        status="unknown",
    )
    db.add(new_ds)
    await db.commit()
    await db.refresh(new_ds)
    return new_ds


def test_connection_params(data: TestConnectionRequest) -> tuple[bool, str]:
    conn = build_connection_info(
        DataSource(
            db_type=data.db_type,
            host=data.host,
            port=data.port,
            username=data.username,
            encrypted_password=encrypt_text(data.password),
            database_name=normalize_database_name(data.db_type, data.database_name),
            ssh_enabled=data.ssh_enabled,
            ssh_host=data.ssh_host,
            ssh_port=data.ssh_port,
            ssh_user=data.ssh_user,
            ssh_auth_type=data.ssh_auth_type,
            ssh_private_key=encrypt_text(data.ssh_private_key),
        )
    )
    return test_connection(conn)


async def test_saved_connection(db: AsyncSession, connection_id: int) -> tuple[bool, str]:
    ds = await get_connection(db, connection_id)
    conn = build_connection_info(ds)
    ok, message = test_connection(conn)
    ds.status = "active" if ok else "error"
    await db.commit()
    return ok, message
