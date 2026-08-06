"""加密与密码哈希测试。"""
from app.security import decrypt_text, encrypt_text, hash_password, verify_password


def test_encrypt_roundtrip():
    token = encrypt_text("secret-password")
    assert token != "secret-password"
    assert decrypt_text(token) == "secret-password"


def test_encrypt_empty():
    assert encrypt_text("") == ""
    assert decrypt_text("") == ""
    assert decrypt_text("invalid-token") == ""


def test_password_hash():
    hashed = hash_password("admin123")
    assert hashed != "admin123"
    assert verify_password("admin123", hashed)
    assert not verify_password("wrong", hashed)
