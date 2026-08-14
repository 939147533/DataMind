"""适配器 execute() 行数据序列化回归测试（MySQL DictCursor / PostgreSQL RealDictCursor 均为 dict 行）。"""
from app.adapters.base import ConnectionInfo
from app.adapters.mysql_adapter import MySQLAdapter
from app.adapters.postgres_adapter import PostgreSQLAdapter


class FakeCursor:
    def __init__(self, rows):
        self._rows = rows
        self.description = (("id",), ("name",))

    def execute(self, sql):
        return None

    def fetchall(self):
        return self._rows

    def __enter__(self):
        return self

    def __exit__(self, *args):
        return False


class FakeConn:
    def __init__(self, rows):
        self._cursor = FakeCursor(rows)

    def cursor(self):
        return self._cursor

    def commit(self):
        pass

    def rollback(self):
        pass

    def close(self):
        pass


def _rows():
    return [{"id": 1, "name": "alice"}, {"id": 2, "name": "bob"}]


def test_mysql_execute_returns_row_values(monkeypatch):
    adapter = MySQLAdapter(ConnectionInfo(db_type="mysql"))
    monkeypatch.setattr(adapter, "connect", lambda: FakeConn(_rows()))
    result = adapter.execute("SELECT id, name FROM users")
    assert result["is_query"] is True
    assert result["columns"] == ["id", "name"]
    assert result["rows"] == [[1, "alice"], [2, "bob"]]


def test_postgres_execute_returns_row_values(monkeypatch):
    adapter = PostgreSQLAdapter(ConnectionInfo(db_type="postgresql"))
    monkeypatch.setattr(adapter, "connect", lambda: FakeConn(_rows()))
    result = adapter.execute("SELECT id, name FROM users")
    assert result["is_query"] is True
    assert result["columns"] == ["id", "name"]
    assert result["rows"] == [[1, "alice"], [2, "bob"]]
