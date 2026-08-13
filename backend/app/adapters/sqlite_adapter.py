"""SQLite 适配器（全链路实现，P0 默认可测数据源）。"""
import sqlite3
from pathlib import Path

from .. import config
from .base import AdapterError, BaseDBAdapter


class SQLiteAdapter(BaseDBAdapter):
    db_type = "sqlite"
    dialect_hint = "SQLite 方言：日期用 strftime('%Y-%m-%d', col)，最近 N 天用 date('now', '-N day')，取前 N 行用 LIMIT N"
    supports_ddl_generate = True

    def _db_path(self) -> Path:
        return config.resolve_data_path(self.conn.database_name or "")

    def connect(self):
        path = self._db_path()
        if not path.exists():
            raise AdapterError(f"数据库文件不存在: {path}")
        try:
            conn = sqlite3.connect(str(path), timeout=30)
            conn.row_factory = sqlite3.Row
            return conn
        except sqlite3.Error as exc:
            raise AdapterError(f"SQLite 连接失败: {exc}") from exc

    def test_connection(self):
        path = self._db_path()
        if not path.exists():
            return False, f"数据库文件不存在: {path}"
        try:
            conn = self.connect()
            conn.execute("SELECT 1")
            self._close(conn)
            return True, "连接成功"
        except Exception as exc:  # noqa: BLE001
            return False, str(exc)

    def _query(self, sql: str, params: tuple = ()) -> list[dict]:
        conn = self.connect()
        try:
            cur = conn.execute(sql, params)
            rows = cur.fetchall()
            return [dict(r) for r in rows]
        except sqlite3.Error as exc:
            raise AdapterError(f"SQL 执行错误: {exc}") from exc
        finally:
            self._close(conn)

    def get_schemas(self) -> list[str]:
        rows = self._query("PRAGMA database_list")
        return [r["name"] for r in rows]

    def get_tables(self, schema: str = "") -> list[str]:
        rows = self._query(
            "SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%' ORDER BY name"
        )
        return [r["name"] for r in rows]

    def get_table_columns(self, table: str, schema: str = "") -> list[dict]:
        rows = self._query(f'PRAGMA table_info("{table}")')
        ddl = self.get_table_ddl(table).upper()
        columns = []
        for r in rows:
            columns.append(
                {
                    "name": r["name"],
                    "data_type": r["type"] or "",
                    "nullable": not bool(r["notnull"]),
                    "default": r["dflt_value"],
                    "primary_key": bool(r["pk"]),
                    "auto_increment": bool(r["pk"]) and "AUTOINCREMENT" in ddl,
                    "comment": "",
                }
            )
        return columns

    def get_table_indexes(self, table: str, schema: str = "") -> list[dict]:
        idx_rows = self._query(f'PRAGMA index_list("{table}")')
        indexes = []
        for idx in idx_rows:
            info = self._query(f'PRAGMA index_info("{idx["name"]}")')
            indexes.append(
                {
                    "name": idx["name"],
                    "unique": bool(idx["unique"]),
                    "columns": [i["name"] for i in info],
                    "type": "INDEX",
                }
            )
        return indexes

    def get_table_ddl(self, table: str, schema: str = "") -> str:
        rows = self._query(
            "SELECT sql FROM sqlite_master WHERE type='table' AND name=?", (table,)
        )
        return rows[0]["sql"] if rows else ""

    def get_table_data(self, table: str, schema: str = "", page: int = 1, size: int = 100) -> dict:
        page = max(1, page)
        size = max(1, min(size, 1000))
        offset = (page - 1) * size
        total = self._query(f'SELECT COUNT(*) AS c FROM "{table}"')[0]["c"]
        rows = self._query(f'SELECT * FROM "{table}" LIMIT ? OFFSET ?', (size, offset))
        columns = list(rows[0].keys()) if rows else [c["name"] for c in self.get_table_columns(table)]
        return {
            "columns": columns,
            "rows": [list(r.values()) for r in rows],
            "total": total,
            "page": page,
            "page_size": size,
        }

    def get_views(self, schema: str = "") -> list[str]:
        rows = self._query("SELECT name FROM sqlite_master WHERE type='view' ORDER BY name")
        return [r["name"] for r in rows]

    def get_view_ddl(self, name: str, schema: str = "") -> str:
        rows = self._query("SELECT sql FROM sqlite_master WHERE type='view' AND name=?", (name,))
        return rows[0]["sql"] if rows else ""

    def get_functions(self, schema: str = "") -> list[str]:
        return []

    def get_procedures(self, schema: str = "") -> list[str]:
        return []

    def get_triggers(self, schema: str = "") -> list[dict]:
        rows = self._query(
            "SELECT name, sql FROM sqlite_master WHERE type='trigger' ORDER BY name"
        )
        return [{"name": r["name"], "sql": r["sql"]} for r in rows]

    def get_trigger_ddl(self, name: str, schema: str = "") -> str:
        rows = self._query(
            "SELECT sql FROM sqlite_master WHERE type='trigger' AND name=?", (name,)
        )
        return rows[0]["sql"] if rows else ""

    def get_sequences(self, schema: str = "") -> list[dict]:
        return []

    def sample_column_values(self, table: str, column: str, schema: str = "") -> list[str]:
        rows = self._query(f'SELECT DISTINCT "{column}" AS v FROM "{table}" WHERE "{column}" IS NOT NULL LIMIT 8')
        return [r["v"] for r in rows]

    def execute(self, sql: str) -> dict:
        conn = self.connect()
        try:
            cur = conn.execute(sql)
            if cur.description:
                columns = [d[0] for d in cur.description]
                rows = cur.fetchall()
                return {
                    "columns": columns,
                    "rows": [list(r) for r in rows],
                    "affected_rows": 0,
                    "is_query": True,
                }
            conn.commit()
            affected = cur.rowcount if cur.rowcount and cur.rowcount >= 0 else 0
            return {
                "columns": [],
                "rows": [],
                "affected_rows": affected,
                "is_query": False,
            }
        except sqlite3.Error as exc:
            conn.rollback()
            raise AdapterError(f"SQL 执行错误: {exc}") from exc
        finally:
            self._close(conn)

    def preview(self, sql: str) -> int:
        """在事务中执行 DML 后回滚，返回将影响的行数。"""
        conn = self.connect()
        try:
            cur = conn.execute(sql)
            affected = cur.rowcount if cur.rowcount and cur.rowcount >= 0 else 0
            conn.rollback()
            return affected
        except sqlite3.Error as exc:
            conn.rollback()
            raise AdapterError(f"影响行数预估失败: {exc}") from exc
        finally:
            self._close(conn)

    def explain(self, sql: str) -> list[dict]:
        return self._query(f"EXPLAIN QUERY PLAN {sql}")
