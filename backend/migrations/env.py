"""Alembic 迁移环境：目标库是应用自身的 SQLite（默认 backend/data/app.db）。

与 `database.init_db()` 的分工：
- 全新安装仍由 create_all 建表（幂等，并补建模型新声明的索引）；
- 已上线库的结构变更走迁移脚本：`alembic upgrade head`；
  首次接入已有库时先 `alembic stamp head` 打基线，避免重复建表。
- 需要临时指向其它库时设 `DATABASE_URL` 环境变量（如 sqlite+aiosqlite:///tmp/x.db）。
"""
import asyncio
import os
from logging.config import fileConfig

from alembic import context
from sqlalchemy import pool
from sqlalchemy.engine import Connection
from sqlalchemy.ext.asyncio import async_engine_from_config

from app import models  # noqa: F401  确保所有表注册进 Base.metadata
from app.database import Base

config = context.config

if config.config_file_name is not None:
    fileConfig(config.config_file_name)

target_metadata = Base.metadata


def _database_url() -> str:
    override = os.environ.get("DATABASE_URL")
    if override:
        return override
    from app.config import APP_DB_PATH

    return f"sqlite+aiosqlite:///{APP_DB_PATH}"


def run_migrations_offline() -> None:
    context.configure(
        url=_database_url(),
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
        render_as_batch=True,
    )
    with context.begin_transaction():
        context.run_migrations()


def do_run_migrations(connection: Connection) -> None:
    # render_as_batch：SQLite 不支持大部分 ALTER，改成“建新表-搬数据-换名”
    context.configure(connection=connection, target_metadata=target_metadata, render_as_batch=True)
    with context.begin_transaction():
        context.run_migrations()


async def run_async_migrations() -> None:
    configuration = config.get_section(config.config_ini_section, {})
    configuration["sqlalchemy.url"] = _database_url()
    connectable = async_engine_from_config(configuration, prefix="sqlalchemy.", poolclass=pool.NullPool)
    async with connectable.connect() as connection:
        await connection.run_sync(do_run_migrations)
    await connectable.dispose()


if context.is_offline_mode():
    run_migrations_offline()
else:
    asyncio.run(run_async_migrations())
