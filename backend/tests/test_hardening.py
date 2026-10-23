"""安全加固：加密密钥来源/权限、管理员初始口令。"""
import stat

import pytest
from cryptography.fernet import Fernet


def test_secret_key_from_env_roundtrip(monkeypatch):
    from app import security

    monkeypatch.setenv("DBAGENT_SECRET_KEY", Fernet.generate_key().decode())
    monkeypatch.setattr(security, "_fernet", None)
    token = security.encrypt_text("p@ssw0rd")
    assert token != "p@ssw0rd"
    assert security.decrypt_text(token) == "p@ssw0rd"


def test_secret_key_file_created_with_restrictive_perms(tmp_path, monkeypatch):
    from app import security

    key_file = tmp_path / "nested" / "secret.key"
    monkeypatch.delenv("DBAGENT_SECRET_KEY", raising=False)
    monkeypatch.setattr(security, "SECRET_KEY_PATH", key_file)
    monkeypatch.setattr(security, "_fernet", None)

    security.warm_up()

    assert key_file.exists()
    assert stat.S_IMODE(key_file.stat().st_mode) == 0o600


def test_invalid_env_key_fails_fast(monkeypatch):
    from app import security

    monkeypatch.setenv("DBAGENT_SECRET_KEY", "not-a-valid-fernet-key")
    monkeypatch.setattr(security, "_fernet", None)
    with pytest.raises(RuntimeError):
        security.encrypt_text("x")


def test_admin_initial_password_can_be_overridden(monkeypatch):
    from app import seed

    monkeypatch.delenv("DBAGENT_ADMIN_PASSWORD", raising=False)
    assert seed.admin_initial_password() == "admin123"

    monkeypatch.setenv("DBAGENT_ADMIN_PASSWORD", "S3cret!23")
    assert seed.admin_initial_password() == "S3cret!23"

    monkeypatch.setenv("DBAGENT_ADMIN_PASSWORD", "   ")
    assert seed.admin_initial_password() == "admin123"


async def test_admin_default_password_is_detected():
    from app.database import SessionLocal
    from app.seed import admin_uses_default_password

    async with SessionLocal() as db:
        assert await admin_uses_default_password(db) is True


async def test_check_sql_permission_rejects_missing_user():
    """D1：user_id 缺失时必须拒绝（fail-closed），不能静默放行。"""
    from fastapi import HTTPException

    from app.database import SessionLocal
    from app.permissions import check_sql_permission

    async with SessionLocal() as db:
        for op_type in ("READ", "DML", "DDL"):
            with pytest.raises(HTTPException) as exc:
                await check_sql_permission(db, None, op_type)
            assert exc.value.status_code == 401


def test_decrypt_text_reports_failure(monkeypatch, caplog):
    """D2：解密失败要留告警且不泄露密文；strict=True 时抛出明确异常。"""
    from app import security

    monkeypatch.setenv("DBAGENT_SECRET_KEY", Fernet.generate_key().decode())
    monkeypatch.setattr(security, "_fernet", None)
    token = security.encrypt_text("secret")

    # 换一把密钥：原密文解不开
    monkeypatch.setenv("DBAGENT_SECRET_KEY", Fernet.generate_key().decode())
    monkeypatch.setattr(security, "_fernet", None)

    with caplog.at_level("WARNING", logger="app.security"):
        assert security.decrypt_text(token, purpose="测试密文") == ""
    assert "解密失败" in caplog.text
    assert token not in caplog.text  # 日志中不得出现密文

    with pytest.raises(security.SecretDecryptError):
        security.decrypt_text(token, purpose="测试密文", strict=True)

    # 空值不是「解密失败」，不应告警
    caplog.clear()
    assert security.decrypt_text("") == ""
    assert caplog.text == ""


class _FakeCursor:
    """模拟 pymysql 的 DictCursor：fetchall 直接返回字典行。"""

    def __init__(self, rows):
        self._rows = rows

    def __enter__(self):
        return self

    def __exit__(self, *_exc):
        return False

    def execute(self, _sql, _params=None):
        return None

    def fetchall(self):
        return self._rows


class _FakeConn:
    def __init__(self, rows):
        self._rows = rows

    def cursor(self):
        return _FakeCursor(self._rows)

    def ping(self, reconnect=False):
        return None

    def rollback(self):
        return None

    def close(self):
        return None


def _mysql_adapter_with(monkeypatch, rows):
    from app.adapters.base import ConnectionInfo
    from app.adapters.mysql_adapter import MySQLAdapter

    adapter = MySQLAdapter(ConnectionInfo(db_type="mysql", host="127.0.0.1", port=3306, database_name="demo"))
    conn = _FakeConn(rows)
    monkeypatch.setattr(adapter, "_acquire_conn", lambda: conn)
    monkeypatch.setattr(adapter, "_release_conn", lambda c, broken=False: None)
    return adapter


def test_mysql_columns_tolerate_uppercase_information_schema_keys(monkeypatch):
    """MySQL 的 information_schema 列名是大写：未起别名的 NUMERIC_PRECISION 曾直接 KeyError。"""
    adapter = _mysql_adapter_with(
        monkeypatch,
        [
            {
                "name": "amount",
                "data_type": "decimal",
                "char_length": None,
                "NUMERIC_PRECISION": 12,
                "NUMERIC_SCALE": 2,
                "nullable": 0,
                "default_value": None,
                "primary_key": 0,
                "auto_increment": 0,
                "comment": "",
            }
        ],
    )
    cols = adapter.get_table_columns("t_order")
    assert cols[0]["name"] == "amount"
    assert cols[0]["length"] == "12,2"


def test_mysql_indexes_tolerate_uppercase_information_schema_keys(monkeypatch):
    """同一个坑：NON_UNIQUE / COLUMN_NAME / INDEX_TYPE 也未起别名。"""
    adapter = _mysql_adapter_with(
        monkeypatch,
        [{"name": "idx_amount", "NON_UNIQUE": 0, "COLUMN_NAME": "amount", "INDEX_TYPE": "BTREE"}],
    )
    assert adapter.get_table_indexes("t_order") == [
        {"name": "idx_amount", "unique": True, "columns": ["amount"], "type": "BTREE"}
    ]


def test_mysql_summary_schemas_prefers_connected_database(monkeypatch):
    """摘要只取当前库，避免 information_schema 等系统库按字母序挤占名额。"""
    adapter = _mysql_adapter_with(monkeypatch, [])
    assert adapter.summary_schemas() == ["demo"]

    adapter.conn.database_name = ""
    monkeypatch.setattr(adapter, "get_schemas", lambda: ["information_schema", "mysql", "sys", "biz", "report"])
    assert adapter.summary_schemas() == ["biz", "report"]
