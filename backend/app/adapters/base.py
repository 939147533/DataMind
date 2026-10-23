"""数据库适配器抽象基类。"""
import re
from abc import ABC, abstractmethod
from dataclasses import dataclass

from .pool import DB_POOL


class AdapterError(Exception):
    """适配器层错误（连接失败、未安装驱动等）。"""


_NUMERIC_LENGTH_TYPES = re.compile(r"decimal|numeric|number", re.IGNORECASE)


def base_data_type(data_type: str = "") -> str:
    """去掉长度/精度修饰并小写，用于表结构对比时的类型比较。"""
    return re.sub(r"\([^)]*\)", "", data_type or "").strip().lower()


def column_length(
    data_type: str = "",
    char_length=None,
    numeric_precision=None,
    numeric_scale=None,
) -> str:
    """规范化列长度/精度：字符类型取字符长度，数值类型取 precision[,scale]，其余返回空串。

    优先使用驱动返回的长度/精度元数据；缺失时回退解析声明类型中的括号部分（如 SQLite 的 VARCHAR(255)）。
    """
    if char_length not in (None, "", 0, "0"):
        try:
            return str(int(char_length))
        except (TypeError, ValueError):
            return str(char_length)
    if numeric_precision not in (None, "", 0, "0") and _NUMERIC_LENGTH_TYPES.search(data_type or ""):
        try:
            precision = str(int(numeric_precision))
            scale = int(numeric_scale) if numeric_scale not in (None, "", 0, "0") else 0
        except (TypeError, ValueError):
            return str(numeric_precision)
        return f"{precision},{scale}" if scale else precision
    match = re.search(r"\(([^)]*)\)", data_type or "")
    return match.group(1).strip() if match else ""


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
    dialect_hint = ""

    # 低基数文本列名匹配：用于 Schema 摘要中附带枚举取值提示
    _enum_column_re = re.compile(
        r"status|state|type|flag|channel|mode|level|risk|grade|category|kind|gender|currency|region|account_type|user_type|cert_type|trans_code",
        re.IGNORECASE,
    )

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

    # ---------- 连接池 ----------
    def _conn_key(self) -> tuple:
        """按连接参数分桶：同一数据源跨请求共享一个连接池。"""
        c = self.conn
        return (self.db_type, c.host, c.port, c.database_name, c.username, c.password)

    def _is_conn_alive(self, conn) -> bool:
        """借出前的生存探测：默认认为活，驱动可覆写。"""
        return True

    def _reset_conn(self, conn) -> None:
        """归还前回滚隐式事务，避免借出后手上残留快照。"""
        conn.rollback()

    def _acquire_conn(self):
        """从池中借出连接（无可用则新建）。"""
        return DB_POOL.acquire(
            self._conn_key(),
            self.connect,
            is_alive=self._is_conn_alive,
            close=self._close,
        )

    def _release_conn(self, conn, *, broken: bool = False) -> None:
        """归还连接：broken 或 reset 失败时丢弃而不污染池。"""
        DB_POOL.release(
            self._conn_key(),
            conn,
            broken=broken,
            reset=self._reset_conn,
            close=self._close,
        )

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

    def get_function_ddl(self, name: str, schema: str = "") -> str:
        return ""

    def get_procedures(self, schema: str = "") -> list[str]:
        return []

    def get_procedure_ddl(self, name: str, schema: str = "") -> str:
        return ""

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

    def sample_column_values(self, table: str, column: str, schema: str = "") -> list[str]:
        """采样文本列的常见取值，用于 Schema 摘要中的枚举提示；默认不采样。"""
        return []

    @classmethod
    def _is_enum_like(cls, col: dict) -> bool:
        name = str(col.get("name") or "")
        data_type = str(col.get("data_type") or "").upper()
        if not cls._enum_column_re.search(name):
            return False
        return any(k in data_type for k in ("CHAR", "VARCHAR", "ENUM", "STRING", "TEXT", "CLOB"))

    def summary_schemas(self) -> list[str]:
        """Schema 摘要要覆盖的 schema 列表（默认取前 5 个）。

        单库连接（MySQL / OceanBase 等）应覆写本方法：否则 information_schema、
        mysql 这类系统库会按字母序排在前面，把真正的业务表挤出摘要。
        """
        return self.get_schemas()[:5]

    def schema_summary(self) -> str:
        """生成供 LLM 使用的 Schema 摘要文本。"""
        parts = []
        for schema in self.summary_schemas():
            for table in self.get_tables(schema)[:20]:
                cols = self.get_table_columns(table, schema)
                col_desc = []
                enum_count = 0
                for c in cols:
                    desc = f"{c['name']} {c['data_type']}"
                    if enum_count < 4 and self._is_enum_like(c):
                        try:
                            vals = [str(v) for v in self.sample_column_values(table, c["name"], schema)]
                            # 单值采样信息量低且可能误导，跳过
                            if len(vals) >= 2:
                                desc += f"[枚举:{'|'.join(vals[:8])}]"
                                enum_count += 1
                        except Exception:  # noqa: BLE001
                            pass
                    col_desc.append(desc)
                parts.append(f"{schema}.{table}({', '.join(col_desc)})")
        return "\n".join(parts)
