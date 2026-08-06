"""适配器注册表：按 db_type 获取适配器。"""
from .base import AdapterError, BaseDBAdapter, ConnectionInfo
from .mongodb_adapter import MongoDBAdapter
from .mysql_adapter import MySQLAdapter
from .oracle_adapter import OracleAdapter
from .postgres_adapter import PostgreSQLAdapter
from .sqlite_adapter import SQLiteAdapter

ADAPTERS: dict[str, type[BaseDBAdapter]] = {
    "sqlite": SQLiteAdapter,
    "mysql": MySQLAdapter,
    "oceanbase": MySQLAdapter,
    "goldendb": MySQLAdapter,
    "postgresql": PostgreSQLAdapter,
    "oracle": OracleAdapter,
    "mongodb": MongoDBAdapter,
}


def get_adapter(conn: ConnectionInfo) -> BaseDBAdapter:
    cls = ADAPTERS.get(conn.db_type)
    if cls is None:
        raise AdapterError(f"不支持的数据库类型: {conn.db_type}")
    return cls(conn)


def test_connection(conn: ConnectionInfo) -> tuple[bool, str]:
    return get_adapter(conn).test_connection()
