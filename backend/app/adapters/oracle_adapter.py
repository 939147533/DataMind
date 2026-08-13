"""Oracle 适配器（oracledb thin 模式）。"""
from .base import AdapterError, BaseDBAdapter


def _import_oracledb():
    try:
        import oracledb
        return oracledb
    except ImportError as exc:
        raise AdapterError("未安装 oracledb，请执行 pip install oracledb") from exc


class OracleAdapter(BaseDBAdapter):
    db_type = "oracle"
    dialect_hint = "Oracle 方言：字符串用单引号，日期用 TO_CHAR/TRUNC，最近 N 天用 TRUNC(SYSDATE)-N，取前 N 行用 FETCH FIRST N ROWS ONLY（不支持 LIMIT）"
    supports_ddl_generate = True

    def _dsn(self) -> str:
        return f"{self.conn.host or 'localhost'}:{self.conn.port or 1521}/{self.conn.database_name or 'ORCL'}"

    def connect(self):
        oracledb = _import_oracledb()
        try:
            return oracledb.connect(
                user=self.conn.username,
                password=self.conn.password,
                dsn=self._dsn(),
            )
        except Exception as exc:  # noqa: BLE001
            raise AdapterError(f"Oracle 连接失败: {exc}") from exc

    def _query(self, sql: str, params: dict | None = None) -> list[dict]:
        conn = self.connect()
        try:
            cur = conn.cursor()
            cur.execute(sql, params or {})
            cols = [d[0] for d in cur.description] if cur.description else []
            rows = []
            for r in cur.fetchall():
                rows.append({cols[i].lower(): v for i, v in enumerate(r)})
            cur.close()
            return rows
        except Exception as exc:  # noqa: BLE001
            raise AdapterError(f"SQL 执行错误: {exc}") from exc
        finally:
            self._close(conn)

    def get_schemas(self) -> list[str]:
        rows = self._query(
            "SELECT username AS name FROM all_users WHERE oracle_maintained='N' ORDER BY username"
        )
        return [r["name"] for r in rows]

    def get_tables(self, schema: str = "") -> list[str]:
        owner = (schema or self.conn.username).upper()
        rows = self._query(
            "SELECT table_name AS name FROM all_tables WHERE owner=:owner ORDER BY table_name",
            {"owner": owner},
        )
        return [r["name"] for r in rows]

    def get_table_columns(self, table: str, schema: str = "") -> list[dict]:
        owner = (schema or self.conn.username).upper()
        rows = self._query(
            "SELECT column_name AS name, data_type AS data_type, nullable, "
            "data_default AS default_value, column_id "
            "FROM all_tab_columns WHERE owner=:owner AND table_name=:tname ORDER BY column_id",
            {"owner": owner, "tname": table.upper()},
        )
        pk_rows = self._query(
            "SELECT cols.column_name AS name FROM all_constraints cons "
            "JOIN all_cons_columns cols ON cons.constraint_name=cols.constraint_name "
            "WHERE cons.owner=:owner AND cons.table_name=:tname AND cons.constraint_type='P'",
            {"owner": owner, "tname": table.upper()},
        )
        pk_cols = {r["name"] for r in pk_rows}
        return [
            {
                "name": r["name"],
                "data_type": r["data_type"] or "",
                "nullable": r["nullable"] == "Y",
                "default": r["default_value"],
                "primary_key": r["name"] in pk_cols,
                "auto_increment": False,
                "comment": "",
            }
            for r in rows
        ]

    def get_table_indexes(self, table: str, schema: str = "") -> list[dict]:
        owner = (schema or self.conn.username).upper()
        rows = self._query(
            "SELECT i.index_name AS name, i.uniqueness, c.column_name "
            "FROM all_indexes i JOIN all_ind_columns c ON i.index_name=c.index_name AND i.owner=c.index_owner "
            "WHERE i.table_owner=:owner AND i.table_name=:tname ORDER BY i.index_name, c.column_position",
            {"owner": owner, "tname": table.upper()},
        )
        grouped: dict[str, dict] = {}
        for r in rows:
            entry = grouped.setdefault(r["name"], {"name": r["name"], "unique": r["uniqueness"] == "UNIQUE", "columns": [], "type": "INDEX"})
            entry["columns"].append(r["column_name"])
        return list(grouped.values())

    def get_table_ddl(self, table: str, schema: str = "") -> str:
        owner = (schema or self.conn.username).upper()
        rows = self._query(
            "SELECT dbms_metadata.get_ddl('TABLE', :name, :owner) AS ddl FROM dual",
            {"name": table.upper(), "owner": owner},
        )
        return rows[0]["ddl"] if rows else ""

    def get_table_data(self, table: str, schema: str = "", page: int = 1, size: int = 100) -> dict:
        owner = (schema or self.conn.username).upper()
        page = max(1, page)
        size = max(1, min(size, 1000))
        total = self._query(
            f"SELECT COUNT(*) AS c FROM {owner}.{table}"
        )[0]["c"]
        rows = self._query(
            f"SELECT * FROM (SELECT a.*, ROWNUM rn FROM {owner}.{table} a WHERE ROWNUM <= :max) "
            "WHERE rn > :offset",
            {"max": page * size, "offset": (page - 1) * size},
        )
        columns = [k.upper() for k in rows[0].keys()] if rows else [c["name"] for c in self.get_table_columns(table)]
        return {"columns": columns, "rows": [list(r.values()) for r in rows], "total": total, "page": page, "page_size": size}

    def get_views(self, schema: str = "") -> list[str]:
        owner = (schema or self.conn.username).upper()
        rows = self._query(
            "SELECT view_name AS name FROM all_views WHERE owner=:owner ORDER BY view_name",
            {"owner": owner},
        )
        return [r["name"] for r in rows]

    def get_view_ddl(self, name: str, schema: str = "") -> str:
        owner = (schema or self.conn.username).upper()
        rows = self._query(
            "SELECT dbms_metadata.get_ddl('VIEW', :name, :owner) AS ddl FROM dual",
            {"name": name.upper(), "owner": owner},
        )
        return rows[0]["ddl"] if rows else ""

    def get_functions(self, schema: str = "") -> list[str]:
        owner = (schema or self.conn.username).upper()
        rows = self._query(
            "SELECT object_name AS name FROM all_objects WHERE owner=:owner AND object_type='FUNCTION' ORDER BY object_name",
            {"owner": owner},
        )
        return [r["name"] for r in rows]

    def get_procedures(self, schema: str = "") -> list[str]:
        owner = (schema or self.conn.username).upper()
        rows = self._query(
            "SELECT object_name AS name FROM all_objects WHERE owner=:owner AND object_type='PROCEDURE' ORDER BY object_name",
            {"owner": owner},
        )
        return [r["name"] for r in rows]

    def get_function_ddl(self, name: str, schema: str = "") -> str:
        owner = (schema or self.conn.username).upper()
        rows = self._query(
            "SELECT dbms_metadata.get_ddl('FUNCTION', :name, :owner) AS ddl FROM dual",
            {"name": name.upper(), "owner": owner},
        )
        return rows[0]["ddl"] if rows else ""

    def get_procedure_ddl(self, name: str, schema: str = "") -> str:
        owner = (schema or self.conn.username).upper()
        rows = self._query(
            "SELECT dbms_metadata.get_ddl('PROCEDURE', :name, :owner) AS ddl FROM dual",
            {"name": name.upper(), "owner": owner},
        )
        return rows[0]["ddl"] if rows else ""

    def get_triggers(self, schema: str = "") -> list[dict]:
        owner = (schema or self.conn.username).upper()
        rows = self._query(
            "SELECT trigger_name AS name FROM all_triggers WHERE owner=:owner ORDER BY trigger_name",
            {"owner": owner},
        )
        return [{"name": r["name"], "sql": ""} for r in rows]

    def get_trigger_ddl(self, name: str, schema: str = "") -> str:
        owner = (schema or self.conn.username).upper()
        rows = self._query(
            "SELECT dbms_metadata.get_ddl('TRIGGER', :name, :owner) AS ddl FROM dual",
            {"name": name.upper(), "owner": owner},
        )
        return rows[0]["ddl"] if rows else ""

    def get_sequences(self, schema: str = "") -> list[dict]:
        owner = (schema or self.conn.username).upper()
        rows = self._query(
            "SELECT sequence_name AS name, last_number AS current_value, increment_by AS incr, "
            "min_value, max_value, cache_size "
            "FROM all_sequences WHERE sequence_owner=:owner ORDER BY sequence_name",
            {"owner": owner},
        )
        return [
            {
                "name": r["name"],
                "current_value": r["current_value"],
                "increment": r["incr"],
                "min_value": r["min_value"],
                "max_value": r["max_value"],
                "cache_size": r["cache_size"],
            }
            for r in rows
        ]

    def sample_column_values(self, table: str, column: str, schema: str = "") -> list[str]:
        owner = (schema or self.conn.username).upper()
        try:
            rows = self._query(
                f'SELECT DISTINCT "{column}" AS v FROM (SELECT "{column}" FROM {owner}."{table}" '
                f'SAMPLE(20) WHERE "{column}" IS NOT NULL)'
            )
            vals = [r["v"] for r in rows[:8]]
            if len(vals) >= 2:
                return vals
        except Exception:  # noqa: BLE001
            pass
        rows = self._query(
            f'SELECT DISTINCT "{column}" AS v FROM {owner}."{table}" WHERE "{column}" IS NOT NULL'
        )
        return [r["v"] for r in rows[:8]]

    def execute(self, sql: str) -> dict:
        conn = self.connect()
        try:
            cur = conn.cursor()
            cur.execute(sql)
            if cur.description:
                columns = [d[0] for d in cur.description]
                rows = [list(r) for r in cur.fetchall()]
                cur.close()
                return {"columns": columns, "rows": rows, "affected_rows": 0, "is_query": True}
            conn.commit()
            affected = cur.rowcount if cur.rowcount and cur.rowcount >= 0 else 0
            cur.close()
            return {"columns": [], "rows": [], "affected_rows": affected, "is_query": False}
        except Exception as exc:  # noqa: BLE001
            conn.rollback()
            raise AdapterError(f"SQL 执行错误: {exc}") from exc
        finally:
            self._close(conn)

    def explain(self, sql: str) -> list[dict]:
        self._query("EXPLAIN PLAN FOR " + sql)
        rows = self._query("SELECT * FROM TABLE(dbms_xplan.display)")
        return [{"detail": " ".join(str(v) for v in r.values())} for r in rows]
