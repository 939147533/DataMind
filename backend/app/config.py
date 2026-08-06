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
