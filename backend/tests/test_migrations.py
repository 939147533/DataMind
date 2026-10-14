"""Alembic 基线迁移测试：upgrade head 建出的结构与模型 create_all 一致。"""
import os
import subprocess
import sys
from pathlib import Path

BACKEND_DIR = Path(__file__).resolve().parents[1]


def _schema(db_path: Path) -> tuple[set, set]:
    from sqlalchemy import create_engine, inspect

    engine = create_engine(f"sqlite:///{db_path}")
    inspector = inspect(engine)
    tables = set(inspector.get_table_names()) - {"alembic_version"}  # 迁移记账表不算业务结构
    indexes = {(t, ix["name"]) for t in tables for ix in inspector.get_indexes(t)}
    engine.dispose()
    return tables, indexes


def test_alembic_upgrade_head_matches_models(tmp_path):
    migrated = tmp_path / "migrated.db"
    env = {**os.environ, "DATABASE_URL": f"sqlite+aiosqlite:///{migrated}"}
    result = subprocess.run(
        [sys.executable, "-m", "alembic", "upgrade", "head"],
        cwd=BACKEND_DIR,
        env=env,
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0, result.stderr

    built = tmp_path / "create_all.db"
    from sqlalchemy import create_engine

    from app import models  # noqa: F401
    from app.database import Base

    engine = create_engine(f"sqlite:///{built}")
    Base.metadata.create_all(engine)
    engine.dispose()

    migrated_tables, migrated_indexes = _schema(migrated)
    built_tables, built_indexes = _schema(built)
    assert migrated_tables == built_tables
    assert migrated_indexes == built_indexes
