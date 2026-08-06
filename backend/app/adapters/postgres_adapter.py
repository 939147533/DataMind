"""PostgreSQL 适配器。"""
from .base import AdapterError, BaseDBAdapter


def _import_psycopg():
    try:
        import psycopg2
        import psycopg2.extras
        return psycopg2, psycopg2.extras
    except ImportError as exc:
        raise AdapterError("未安装 psycopg2-binary，请执行 pip install psycopg2-binary") from exc


class PostgreSQLAdapter(BaseDBAdapter):
    db_type = "postgresql"
    supports_ddl_generate = True

    def connect(self):
        psycopg2, extras = _import_psycopg()
        try:
            return psycopg2.connect(
                host=self.conn.host or "localhost",
                port=self.conn.port or 5432,
                user=self.conn.username,
                password=self.conn.password,
                dbname=self.conn.database_name or "postgres",
                connect_timeout=10,
                cursor_factory=extras.RealDictCursor,
            )
        except Exception as exc:  # noqa: BLE001
            raise AdapterError(f"PostgreSQL 连接失败: {exc}") from exc

    def _query(self, sql: str, params: tuple | None = None) -> list[dict]:
        conn = self.connect()
        try:
            with conn.cursor() as cur:
                cur.execute(sql, params)
                if cur.description is None:
                    return []
                return [dict(r) for r in cur.fetchall()]
        except Exception as exc:  # noqa: BLE001
            raise AdapterError(f"SQL 执行错误: {exc}") from exc
        finally:
            self._close(conn)

    def _db(self) -> str:
        return self.conn.database_name or "public"

    def get_schemas(self) -> list[str]:
        rows = self._query(
            "SELECT schema_name AS name FROM information_schema.schemata "
            "WHERE schema_name NOT IN ('pg_catalog','information_schema','pg_toast') ORDER BY schema_name"
        )
        return [r["name"] for r in rows]

    def get_tables(self, schema: str = "") -> list[str]:
        sch = schema or "public"
        rows = self._query(
            "SELECT table_name AS name FROM information_schema.tables "
            "WHERE table_schema=%s AND table_type='BASE TABLE' ORDER BY table_name",
            (sch,),
        )
        return [r["name"] for r in rows]

    def get_table_columns(self, table: str, schema: str = "") -> list[dict]:
        sch = schema or "public"
        rows = self._query(
            "SELECT column_name AS name, data_type AS data_type, is_nullable='YES' AS nullable, "
            "column_default AS default_value, is_identity='YES' AS auto_increment, "
            "COALESCE((SELECT true FROM pg_index i JOIN pg_attribute a ON a.attrelid=i.indrelid "
            "AND a.attnum=ANY(i.indkey) WHERE i.indrelid=(quote_ident(%s)||'.'||quote_ident(%s))::regclass "
            "AND i.indisprimary AND a.attname=c.column_name), false) AS primary_key "
            "FROM information_schema.columns c "
            "WHERE table_schema=%s AND table_name=%s ORDER BY ordinal_position",
            (sch, table, sch, table),
        )
        return [
            {
                "name": r["name"],
                "data_type": r["data_type"] or "",
                "nullable": bool(r["nullable"]),
                "default": r["default_value"],
                "primary_key": bool(r["primary_key"]),
                "auto_increment": bool(r["auto_increment"]),
                "comment": "",
            }
            for r in rows
        ]

    def get_table_indexes(self, table: str, schema: str = "") -> list[dict]:
        sch = schema or "public"
        rows = self._query(
            "SELECT indexname AS name, indexdef FROM pg_indexes "
            "WHERE schemaname=%s AND tablename=%s ORDER BY indexname",
            (sch, table),
        )
        return [{"name": r["name"], "unique": "UNIQUE" in (r["indexdef"] or "").upper(), "columns": [], "type": "INDEX", "definition": r["indexdef"]} for r in rows]

    def get_table_ddl(self, table: str, schema: str = "") -> str:
        sch = schema or "public"
        columns = self.get_table_columns(table, sch)
        indexes = self.get_table_indexes(table, sch)
        lines = [f"CREATE TABLE {sch}.{table} ("]
        col_lines = []
        for c in columns:
            parts = [f"    {c['name']} {c['data_type']}"]
            if c["primary_key"]:
                parts.append("PRIMARY KEY")
            elif not c["nullable"]:
                parts.append("NOT NULL")
            if c["default"]:
                parts.append(f"DEFAULT {c['default']}")
            col_lines.append(" ".join(parts))
        lines.append(",\n".join(col_lines))
        lines.append(");")
        for idx in indexes:
            if idx.get("definition"):
                lines.append(idx["definition"] + ";")
        return "\n".join(lines)

    def get_table_data(self, table: str, schema: str = "", page: int = 1, size: int = 100) -> dict:
        sch = schema or "public"
        page = max(1, page)
        size = max(1, min(size, 1000))
        offset = (page - 1) * size
        total = self._query(f'SELECT COUNT(*) AS c FROM "{sch}"."{table}"')[0]["c"]
        rows = self._query(f'SELECT * FROM "{sch}"."{table}" LIMIT %s OFFSET %s', (size, offset))
        columns = list(rows[0].keys()) if rows else [c["name"] for c in self.get_table_columns(table)]
        return {"columns": columns, "rows": [list(r.values()) for r in rows], "total": total, "page": page, "page_size": size}

    def get_views(self, schema: str = "") -> list[str]:
        sch = schema or "public"
        rows = self._query(
            "SELECT table_name AS name FROM information_schema.views WHERE table_schema=%s ORDER BY table_name",
            (sch,),
        )
        return [r["name"] for r in rows]

    def get_view_ddl(self, name: str, schema: str = "") -> str:
        sch = schema or "public"
        rows = self._query("SELECT pg_get_viewdef(%s::regclass, true) AS ddl", (f"{sch}.{name}",))
        return f"CREATE VIEW {sch}.{name} AS\n" + (rows[0]["ddl"] if rows else "")

    def get_functions(self, schema: str = "") -> list[str]:
        sch = schema or "public"
        rows = self._query(
            "SELECT p.proname AS name FROM pg_proc p JOIN pg_namespace n ON n.oid=p.pronamespace "
            "WHERE n.nspname=%s AND p.prokind='f' ORDER BY p.proname",
            (sch,),
        )
        return [r["name"] for r in rows]

    def get_procedures(self, schema: str = "") -> list[str]:
        sch = schema or "public"
        rows = self._query(
            "SELECT p.proname AS name FROM pg_proc p JOIN pg_namespace n ON n.oid=p.pronamespace "
            "WHERE n.nspname=%s AND p.prokind='p' ORDER BY p.proname",
            (sch,),
        )
        return [r["name"] for r in rows]

    def get_triggers(self, schema: str = "") -> list[dict]:
        sch = schema or "public"
        rows = self._query(
            "SELECT tgname AS name FROM pg_trigger t JOIN pg_class c ON c.oid=t.tgrelid "
            "JOIN pg_namespace n ON n.oid=c.relnamespace WHERE n.nspname=%s AND NOT t.tgisinternal ORDER BY tgname",
            (sch,),
        )
        return [{"name": r["name"], "sql": ""} for r in rows]

    def get_trigger_ddl(self, name: str, schema: str = "") -> str:
        return ""

    def get_sequences(self, schema: str = "") -> list[dict]:
        sch = schema or "public"
        rows = self._query(
            "SELECT c.relname AS name FROM pg_class c JOIN pg_namespace n ON n.oid=c.relnamespace "
            "WHERE n.nspname=%s AND c.relkind='S' ORDER BY c.relname",
            (sch,),
        )
        return [{"name": r["name"], "current_value": None, "increment": None} for r in rows]

    def execute(self, sql: str) -> dict:
        psycopg2, _ = _import_psycopg()
        conn = self.connect()
        try:
            with conn.cursor() as cur:
                cur.execute(sql)
                if cur.description:
                    columns = [d[0] for d in cur.description]
                    rows = [list(r) for r in cur.fetchall()]
                    return {"columns": columns, "rows": rows, "affected_rows": 0, "is_query": True}
                conn.commit()
                return {"columns": [], "rows": [], "affected_rows": cur.rowcount, "is_query": False}
        except Exception as exc:  # noqa: BLE001
            conn.rollback()
            raise AdapterError(f"SQL 执行错误: {exc}") from exc
        finally:
            self._close(conn)

    def explain(self, sql: str) -> list[dict]:
        rows = self._query(f"EXPLAIN {sql}")
        return [{"detail": " ".join(str(v) for v in r.values())} for r in rows]
