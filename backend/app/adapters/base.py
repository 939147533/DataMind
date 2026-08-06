"""数据库适配器抽象基类。"""
from abc import ABC, abstractmethod
from dataclasses import dataclass, field


class AdapterError(Exception):
    """适配器层错误（连接失败、未安装驱动等）。"""


@dataclass
class ConnectionInfo:
    db_type: str = "sqlite"
    host: str = ""
    port: int | None = None
    username: str = ""
    password: str = ""
    database_name: str = ""
    ssh_enabled: bool = False
    ssh_host: str = ""
    ssh_port: int = 22
    ssh_user: str = ""
    ssh_auth_type: str = "password"
    ssh_private_key: str = ""

    def display(self) -> str:
        if self.db_type == "sqlite":
            return self.database_name or "demo.db"
        return f"{self.host}:{self.port or ''}/{self.database_name}"


class BaseDBAdapter(ABC):
    """所有数据库适配器需实现的统一接口。"""

    db_type = "base"
    supports_ddl_generate = False

    def __init__(self, conn: ConnectionInfo):
        self.conn = conn

    # ---------- 连接 ----------
    @abstractmethod
    def connect(self):
        """建立连接并返回连接对象。"""

    def test_connection(self) -> tuple[bool, str]:
        try:
            conn = self.connect()
            self._close(conn)
            return True, "连接成功"
        except AdapterError:
            raise
        except Exception as exc:  # noqa: BLE001
            return False, str(exc)

    def _close(self, conn) -> None:
        try:
            conn.close()
        except Exception:
            pass

    # ---------- 元数据 ----------
    @abstractmethod
    def get_schemas(self) -> list[str]: ...

    @abstractmethod
    def get_tables(self, schema: str = "") -> list[str]: ...

    @abstractmethod
    def get_table_columns(self, table: str, schema: str = "") -> list[dict]: ...

    def get_table_indexes(self, table: str, schema: str = "") -> list[dict]:
        return []

    def get_table_ddl(self, table: str, schema: str = "") -> str:
        return ""

    def get_table_data(self, table: str, schema: str = "", page: int = 1, size: int = 100) -> dict:
        raise AdapterError(f"{self.db_type} 暂不支持表数据读取")

    def get_views(self, schema: str = "") -> list[str]:
        return []

    def get_view_ddl(self, name: str, schema: str = "") -> str:
        return ""

    def get_functions(self, schema: str = "") -> list[str]:
        return []

    def get_procedures(self, schema: str = "") -> list[str]:
        return []

    def get_triggers(self, schema: str = "") -> list[str]:
        return []

    def get_trigger_ddl(self, name: str, schema: str = "") -> str:
        return ""

    def get_sequences(self, schema: str = "") -> list[dict]:
        return []

    # ---------- SQL ----------
    @abstractmethod
    def execute(self, sql: str) -> dict:
        """执行单条 SQL，返回 {columns, rows, affected_rows, ...}。"""

    def explain(self, sql: str) -> list[dict]:
        raise AdapterError(f"{self.db_type} 暂不支持执行计划分析")

    def schema_summary(self) -> str:
        """生成供 LLM 使用的 Schema 摘要文本。"""
        parts = []
        for schema in self.get_schemas()[:5]:
            for table in self.get_tables(schema)[:20]:
                cols = self.get_table_columns(table, schema)
                col_desc = ", ".join(f"{c['name']} {c['data_type']}" for c in cols)
                parts.append(f"{schema}.{table}({col_desc})")
        return "\n".join(parts)
