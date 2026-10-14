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
