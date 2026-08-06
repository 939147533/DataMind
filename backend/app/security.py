"""Fernet 加密与密码哈希。"""
import secrets

from cryptography.fernet import Fernet
from passlib.hash import pbkdf2_sha256

from .config import SECRET_KEY_PATH

_fernet: Fernet | None = None


def _get_fernet() -> Fernet:
    global _fernet
    if _fernet is None:
        if not SECRET_KEY_PATH.exists():
            SECRET_KEY_PATH.write_bytes(Fernet.generate_key())
        _fernet = Fernet(SECRET_KEY_PATH.read_bytes())
    return _fernet


def encrypt_text(plain: str | None) -> str:
    if not plain:
        return ""
    return _get_fernet().encrypt(plain.encode("utf-8")).decode("utf-8")


def decrypt_text(token: str | None) -> str:
    if not token:
        return ""
    try:
        return _get_fernet().decrypt(token.encode("utf-8")).decode("utf-8")
    except Exception:
        return ""


def hash_password(password: str) -> str:
    return pbkdf2_sha256.hash(password)


def verify_password(password: str, password_hash: str) -> bool:
    try:
        return pbkdf2_sha256.verify(password, password_hash)
    except Exception:
        return False


def generate_token() -> str:
    return secrets.token_urlsafe(32)
