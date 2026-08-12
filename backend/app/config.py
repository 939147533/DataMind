"""应用配置：路径、常量。支持 DBAGENT_DATA_DIR 环境变量覆盖数据目录（测试用）。"""
import os
from pathlib import Path

BACKEND_DIR = Path(__file__).resolve().parent.parent
DATA_DIR = Path(os.environ.get("DBAGENT_DATA_DIR", str(BACKEND_DIR / "data")))
DRIVERS_DIR = DATA_DIR / "drivers"
EXPORTS_DIR = DATA_DIR / "exports"

APP_DB_PATH = DATA_DIR / "app.db"
DEMO_DB_PATH = DATA_DIR / "demo.db"
SECRET_KEY_PATH = DATA_DIR / "secret.key"

SESSION_TTL_SECONDS = 24 * 60 * 60
EXECUTION_CONFIRM_TIMEOUT = 5 * 60
SQL_EXECUTE_TIMEOUT = 30
MAX_ROWS_PER_PAGE = 1000

DEFAULT_USERNAME = "admin"
DEFAULT_PASSWORD = "admin123"

DEFAULT_DB_TYPES = [
    "oracle", "oceanbase", "goldendb", "mysql",
    "postgresql", "sqlite", "mongodb",
]

DEFAULT_PORTS = {
    "oracle": 1521,
    "oceanbase": 2881,
    "goldendb": 3306,
    "mysql": 3306,
    "postgresql": 5432,
    "sqlite": None,
    "mongodb": 27017,
}


def ensure_dirs() -> None:
    for d in (DATA_DIR, DRIVERS_DIR, EXPORTS_DIR):
        d.mkdir(parents=True, exist_ok=True)


def resolve_data_path(path: str | Path) -> Path:
    """将入库路径解析为绝对路径：相对路径按数据目录解析，失效的旧绝对路径按文件名回退定位（项目改名后自动修复）。"""
    name = str(path or "").strip()
    if not name:
        return DEMO_DB_PATH
    p = Path(name)
    if not p.is_absolute():
        return DATA_DIR / p
    if p.exists():
        return p
    alt = DATA_DIR / p.name
    if alt.exists():
        return alt
    return p


def to_data_relative(path: str | Path) -> str:
    """将路径转为相对数据目录的路径；数据目录之外的绝对路径保持不变。"""
    name = str(path or "").strip()
    if not name:
        return name
    p = Path(name)
    if not p.is_absolute():
        return name
    try:
        return str(p.resolve().relative_to(DATA_DIR.resolve()))
    except ValueError:
        return name


def normalize_database_name(db_type: str, name: str) -> str:
    """SQLite 连接入库前规范化：数据目录内的路径统一存储为相对路径。"""
    if (db_type or "").lower() != "sqlite":
        return name or ""
    return to_data_relative(name) if (name or "").strip() else ""

