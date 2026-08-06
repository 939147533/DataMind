"""MongoDB 适配器（P2：连接测试 + 集合元数据）。"""
from bson import ObjectId

from .base import AdapterError, BaseDBAdapter


def _import_pymongo():
    try:
        import pymongo
        return pymongo
    except ImportError as exc:
        raise AdapterError("未安装 pymongo，请执行 pip install pymongo") from exc


def _clean(value):
    if isinstance(value, ObjectId):
        return str(value)
    if isinstance(value, dict):
        return {k: _clean(v) for k, v in list(value.items())[:50]}
    if isinstance(value, list):
        return [_clean(v) for v in value[:50]]
    return str(value) if hasattr(value, "isoformat") else value


class MongoDBAdapter(BaseDBAdapter):
    db_type = "mongodb"

    def connect(self):
        pymongo = _import_pymongo()
        try:
            uri = f"mongodb://{self.conn.host or 'localhost'}:{self.conn.port or 27017}/"
            client = pymongo.MongoClient(uri, serverSelectionTimeoutMS=5000)
            client.admin.command("ping")
            return client
        except Exception as exc:  # noqa: BLE001
            raise AdapterError(f"MongoDB 连接失败: {exc}") from exc

    def test_connection(self):
        try:
            client = self.connect()
            self._close(client)
            return True, "连接成功"
        except Exception as exc:  # noqa: BLE001
            return False, str(exc)

    def get_schemas(self) -> list[str]:
        client = self.connect()
        try:
            return client.list_database_names()
        finally:
            self._close(client)

    def _db(self):
        pymongo = _import_pymongo()
        client = self.connect()
        name = self.conn.database_name or "admin"
        return client, client[name]

    def get_tables(self, schema: str = "") -> list[str]:
        client, db = self._db()
        try:
            return db.list_collection_names()
        finally:
            self._close(client)

    def get_table_columns(self, table: str, schema: str = "") -> list[dict]:
        client, db = self._db()
        try:
            doc = db[table].find_one()
            if not doc:
                return []
            keys = list(doc.keys())
            return [{"name": k, "data_type": type(doc[k]).__name__, "nullable": True, "default": None, "primary_key": k == "_id", "auto_increment": False, "comment": ""} for k in keys]
        finally:
            self._close(client)

    def get_table_data(self, table: str, schema: str = "", page: int = 1, size: int = 100) -> dict:
        client, db = self._db()
        try:
            total = db[table].count_documents({})
            docs = list(db[table].find().skip((page - 1) * size).limit(size))
            columns = list(docs[0].keys()) if docs else []
            rows = [[_clean(d.get(c)) for c in columns] for d in docs]
            return {"columns": columns, "rows": rows, "total": total, "page": page, "page_size": size}
        finally:
            self._close(client)

    def get_views(self, schema: str = "") -> list[str]:
        client, db = self._db()
        try:
            return [c["name"] for c in db.list_collections() if c.get("type") == "view"]
        finally:
            self._close(client)

    def execute(self, sql: str) -> dict:
        raise AdapterError("MongoDB 不支持 SQL 执行，请在 SQL 工作台选择其他数据源")
