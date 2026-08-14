"""MySQL 适配器（OceanBase / GoldenDB 复用本适配器，协议兼容）。"""
from .base import AdapterError, BaseDBAdapter


def _import_pymysql():
    try:
        import pymysql
        return pymysql
    except ImportError as exc:
        raise AdapterError("未安装 pymysql，请执行 pip install pymysql") from exc


class MySQLAdapter(BaseDBAdapter):
    db_type = "mysql"
    dialect_hint = "MySQL 方言：日期用 DATE_FORMAT(col, '%Y-%m-%d')，最近 N 天用 DATE_SUB(NOW(), INTERVAL N DAY)，取前 N 行用 LIMIT N，标识符用反引号"
    supports_ddl_generate = True

    def connect(self):
        pymysql = _import_pymysql()
        try:
            return pymysql.connect(
                host=self.conn.host or "localhost",
                port=self.conn.port or 3306,
                user=self.conn.username,
                password=self.conn.password,
                database=self.conn.database_name or None,
                charset="utf8mb4",
                connect_timeout=10,
                cursorclass=pymysql.cursors.DictCursor,
            )
        except Exception as exc:  # noqa: BLE001
            raise AdapterError(f"MySQL 连接失败: {exc}") from exc

    def _query(self, sql: str, params: tuple | None = None) -> list[dict]:
        conn = self.connect()
        try:
            with conn.cursor() as cur:
                cur.execute(sql, params)
                return list(cur.fetchall())
        except Exception as exc:  # noqa: BLE001
            raise AdapterError(f"SQL 执行错误: {exc}") from exc
        finally:
            self._close(conn)

    def _db(self) -> str:
        return self.conn.database_name or ""

    def get_schemas(self) -> list[str]:
        rows = self._query(
            "SELECT schema_name AS name FROM information_schema.schemata ORDER BY schema_name"
        )
        return [r["name"] for r in rows]

    def get_tables(self, schema: str = "") -> list[str]:
        db = schema or self._db()
        if not db:
            raise AdapterError("请指定数据库名（database_name）")
        rows = self._query(
            "SELECT table_name AS name FROM information_schema.tables "
            "WHERE table_schema=%s AND table_type='BASE TABLE' ORDER BY table_name",
            (db,),
        )
        return [r["name"] for r in rows]

    def get_table_columns(self, table: str, schema: str = "") -> list[dict]:
        db = schema or self._db()
        rows = self._query(
            "SELECT column_name AS name, data_type AS data_type, "
            "is_nullable='YES' AS nullable, column_default AS default_value, "
            "column_key='PRI' AS primary_key, extra LIKE '%%auto_increment%%' AS auto_increment, "
            "column_comment AS comment "
            "FROM information_schema.columns WHERE table_schema=%s AND table_name=%s "
            "ORDER BY ordinal_position",
            (db, table),
        )
        return [
            {
                "name": r["name"],
                "data_type": r["data_type"] or "",
                "nullable": bool(r["nullable"]),
                "default": r["default_value"],
                "primary_key": bool(r["primary_key"]),
                "auto_increment": bool(r["auto_increment"]),
                "comment": r["comment"] or "",
            }
            for r in rows
        ]

    def get_table_indexes(self, table: str, schema: str = "") -> list[dict]:
        db = schema or self._db()
        rows = self._query(
            "SELECT index_name AS name, non_unique, column_name, index_type "
            "FROM information_schema.statistics WHERE table_schema=%s AND table_name=%s "
            "ORDER BY index_name, seq_in_index",
            (db, table),
        )
        grouped: dict[str, dict] = {}
        for r in rows:
            entry = grouped.setdefault(
                r["name"], {"name": r["name"], "unique": not bool(r["non_unique"]), "columns": [], "type": r["index_type"]}
            )
            entry["columns"].append(r["column_name"])
        return list(grouped.values())

    def get_table_ddl(self, table: str, schema: str = "") -> str:
        rows = self._query(f"SHOW CREATE TABLE `{table}`")
        if rows:
            first = rows[0]
            return first.get("Create Table") or first.get("Table") or ""
        return ""

    def get_table_data(self, table: str, schema: str = "", page: int = 1, size: int = 100) -> dict:
        db = schema or self._db()
        page = max(1, page)
        size = max(1, min(size, 1000))
        offset = (page - 1) * size
        total = self._query(f"SELECT COUNT(*) AS c FROM `{db}`.`{table}`")[0]["c"]
        rows = self._query(f"SELECT * FROM `{db}`.`{table}` LIMIT %s OFFSET %s", (size, offset))
        columns = list(rows[0].keys()) if rows else [c["name"] for c in self.get_table_columns(table)]
        return {"columns": columns, "rows": [list(r.values()) for r in rows], "total": total, "page": page, "page_size": size}

    def get_views(self, schema: str = "") -> list[str]:
        db = schema or self._db()
        rows = self._query(
            "SELECT table_name AS name FROM information_schema.views WHERE table_schema=%s ORDER BY table_name",
            (db,),
        )
        return [r["name"] for r in rows]

    def get_view_ddl(self, name: str, schema: str = "") -> str:
        rows = self._query(f"SHOW CREATE VIEW `{name}`")
        if rows:
            first = rows[0]
            return first.get("Create View") or first.get("View") or ""
        return ""

    def get_functions(self, schema: str = "") -> list[str]:
        db = schema or self._db()
        rows = self._query(
            "SELECT routine_name AS name FROM information_schema.routines "
            "WHERE routine_schema=%s AND routine_type='FUNCTION' ORDER BY routine_name",
            (db,),
        )
        return [r["name"] for r in rows]

    def get_procedures(self, schema: str = "") -> list[str]:
        db = schema or self._db()
        rows = self._query(
            "SELECT routine_name AS name FROM information_schema.routines "
            "WHERE routine_schema=%s AND routine_type='PROCEDURE' ORDER BY routine_name",
            (db,),
        )
        return [r["name"] for r in rows]

    def get_function_ddl(self, name: str, schema: str = "") -> str:
        db = schema or self._db()
        try:
            rows = self._query(f"SHOW CREATE FUNCTION `{db}`.`{name}`")
            if rows:
                return rows[0].get("Create Function") or rows[0].get("Function") or ""
        except AdapterError:
            pass
        return ""

    def get_procedure_ddl(self, name: str, schema: str = "") -> str:
        db = schema or self._db()
        try:
            rows = self._query(f"SHOW CREATE PROCEDURE `{db}`.`{name}`")
            if rows:
                return rows[0].get("Create Procedure") or rows[0].get("Procedure") or ""
        except AdapterError:
            pass
        return ""

    def get_triggers(self, schema: str = "") -> list[dict]:
        db = schema or self._db()
        rows = self._query(
            "SELECT trigger_name AS name FROM information_schema.triggers "
            "WHERE trigger_schema=%s ORDER BY trigger_name",
            (db,),
        )
        return [{"name": r["name"], "sql": ""} for r in rows]

    def get_trigger_ddl(self, name: str, schema: str = "") -> str:
        try:
            rows = self._query(f"SHOW CREATE TRIGGER `{name}`")
            if rows:
                return rows[0].get("SQL Original Statement") or rows[0].get("Create Trigger") or ""
        except AdapterError:
            pass
        return ""

    def get_sequences(self, schema: str = "") -> list[dict]:
        return []

    def sample_column_values(self, table: str, column: str, schema: str = "") -> list[str]:
        db = schema or self._db()
        rows = self._query(
            f'SELECT DISTINCT `{column}` AS v FROM `{db}`.`{table}` WHERE `{column}` IS NOT NULL LIMIT 8'
        )
        return [r["v"] for r in rows]

    def execute(self, sql: str) -> dict:
        conn = self.connect()
        try:
            with conn.cursor() as cur:
                cur.execute(sql)
                if cur.description:
                    columns = [d[0] for d in cur.description]
                    rows = cur.fetchall()
                    return {"columns": columns, "rows": [list(r.values()) for r in rows], "affected_rows": 0, "is_query": True}
                conn.commit()
                return {"columns": [], "rows": [], "affected_rows": cur.rowcount, "is_query": False}
        except Exception as exc:  # noqa: BLE001
            conn.rollback()
            raise AdapterError(f"SQL 执行错误: {exc}") from exc
        finally:
            self._close(conn)

    def explain(self, sql: str) -> list[dict]:
        return self._query(f"EXPLAIN {sql}")
