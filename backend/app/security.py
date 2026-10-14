"""Fernet 加密与密码哈希。"""
import logging
import os
import secrets
import stat

from cryptography.fernet import Fernet
from passlib.hash import pbkdf2_sha256

from .config import SECRET_KEY_PATH

logger = logging.getLogger(__name__)

_fernet: Fernet | None = None


def _warn_if_key_permissive(path) -> None:
    try:
        mode = path.stat().st_mode
    except OSError:
        return
    if mode & (stat.S_IRWXG | stat.S_IRWXO):
        logger.warning(
            "加密密钥 %s 权限过宽（%s），同机其他账号可读，建议 chmod 600 或用 DBAGENT_SECRET_KEY 从环境变量注入",
            path,
            oct(stat.S_IMODE(mode)),
        )


def _load_key() -> bytes:
    """密钥优先取环境变量（生产推荐），否则读密钥文件；没有就生成一份并收紧权限。"""
    env_key = os.environ.get("DBAGENT_SECRET_KEY", "").strip()
    if env_key:
        return env_key.encode("utf-8")
    if not SECRET_KEY_PATH.exists():
        SECRET_KEY_PATH.parent.mkdir(parents=True, exist_ok=True)
        SECRET_KEY_PATH.write_bytes(Fernet.generate_key())
        try:
            os.chmod(SECRET_KEY_PATH, 0o600)
        except OSError:  # Windows 等不支持 chmod 的场景
            pass
        logger.warning(
            "已生成新的加密密钥 %s：数据目录一旦丢失或更换，已加密的密码与 API Key 将无法解密；"
            "生产环境建议用 DBAGENT_SECRET_KEY 环境变量或 DBAGENT_SECRET_KEY_FILE 独立挂载",
            SECRET_KEY_PATH,
        )
    else:
        _warn_if_key_permissive(SECRET_KEY_PATH)
    return SECRET_KEY_PATH.read_bytes()


def _get_fernet() -> Fernet:
    global _fernet
    if _fernet is None:
        try:
            _fernet = Fernet(_load_key())
        except Exception as exc:  # noqa: BLE001
            raise RuntimeError(f"加密密钥不可用（检查 DBAGENT_SECRET_KEY 与 {SECRET_KEY_PATH}）: {exc}") from exc
    return _fernet


def warm_up() -> None:
    """启动时预加载密钥，让“新生成/权限过宽/不可用”在启动日志里就能被发现。"""
    _get_fernet()


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
