"""目标库连接池测试：复用、失效丢弃、上限与 TTL。"""
import time

import pytest

from app.adapters.base import AdapterError, BaseDBAdapter, ConnectionInfo
from app.adapters.pool import ConnectionPool


class FakeConn:
    def __init__(self, name="c1"):
        self.name = name
        self.closed = False
        self.alive = True
        self.rolled_back = 0

    def ping(self, reconnect=False):
        if not self.alive:
            raise RuntimeError("gone")

    def rollback(self):
        self.rolled_back += 1

    def close(self):
        self.closed = True


class FakeCursor:
    def __init__(self, conn):
        self.conn = conn

    def __enter__(self):
        return self

    def __exit__(self, *args):
        return False

    def execute(self, sql, params=None):
        self.sql = sql

    def fetchall(self):
        return [{"ok": 1}]


class FakeAdapter(BaseDBAdapter):
    """不依赖任何驱动的最小适配器，用于验证连接池装配。"""

    db_type = "fake"

    def __init__(self, conn: ConnectionInfo):
        super().__init__(conn)
        self.connects = 0

    def connect(self):
        self.connects += 1
        return FakeConn(f"conn-{self.connects}")

    def _query(self, sql, params=None):
        conn = self._acquire_conn()
        ok = False
        try:
            rows = [{"ok": 1}]
            ok = True
            return rows
        finally:
            self._release_conn(conn, broken=not ok)

    # 抽象方法占位
    def get_schemas(self):
        return []

    def get_tables(self, schema=""):
        return []

    def get_table_columns(self, table, schema=""):
        return []

    def execute(self, sql):
        return {}


def _reset_pool(monkeypatch):
    pool = ConnectionPool(max_size=8, idle_ttl=300.0)
    monkeypatch.setattr("app.adapters.base.DB_POOL", pool, raising=False)
    return pool


def test_connection_is_reused(monkeypatch):
    pool = _reset_pool(monkeypatch)
    adapter = FakeAdapter(ConnectionInfo(db_type="fake", host="h", database_name="d"))
    adapter._query("SELECT 1")
    adapter._query("SELECT 2")
    assert adapter.connects == 1, "第二次查询应复用池中连接"
    assert pool.stats()["reused"] == 1


def test_broken_connection_is_discarded(monkeypatch):
    pool = _reset_pool(monkeypatch)
    adapter = FakeAdapter(ConnectionInfo(db_type="fake", host="h", database_name="d"))
    conn = adapter._acquire_conn()
    adapter._release_conn(conn, broken=True)
    assert conn.closed is True
    assert pool.stats()["idle"] == 0

    fresh = adapter._acquire_conn()
    assert fresh is not conn
    assert adapter.connects == 2


def test_dead_connection_is_replaced(monkeypatch):
    _reset_pool(monkeypatch)
    adapter = FakeAdapter(ConnectionInfo(db_type="fake", host="h", database_name="d"))
    adapter._is_conn_alive = lambda conn: conn.alive
    conn = adapter._acquire_conn()
    conn.alive = False
    adapter._release_conn(conn)
    replacement = adapter._acquire_conn()
    assert replacement is not conn
    assert conn.closed is True


def test_reset_failure_discards_connection(monkeypatch):
    pool = _reset_pool(monkeypatch)
    pool.release(
        ("k",),
        FakeConn(),
        reset=lambda conn: (_ for _ in ()).throw(RuntimeError("rollback failed")),
        close=lambda conn: conn.close(),
    )
    assert pool.stats()["idle"] == 0
    assert pool.stats()["closed"] == 1


def test_idle_ttl_expires_connection(monkeypatch):
    pool = ConnectionPool(max_size=4, idle_ttl=0.01)
    made = []

    def factory():
        conn = FakeConn()
        made.append(conn)
        return conn

    first = pool.acquire(("k",), factory)
    pool.release(("k",), first, close=lambda c: c.close())
    time.sleep(0.02)
    second = pool.acquire(("k",), factory, close=lambda c: c.close())
    assert second is not first
    assert first.closed is True
    assert len(made) == 2


def test_pool_size_cap_closes_extra_connections():
    pool = ConnectionPool(max_size=1, idle_ttl=300.0)
    a, b = FakeConn("a"), FakeConn("b")
    pool.release(("k",), a, close=lambda c: c.close())
    pool.release(("k",), b, close=lambda c: c.close())
    assert pool.stats()["idle"] == 1
    assert b.closed is True
    assert a.closed is False


def test_conn_key_differs_per_datasource():
    a = FakeAdapter(ConnectionInfo(db_type="fake", host="h1", database_name="d"))
    b = FakeAdapter(ConnectionInfo(db_type="fake", host="h2", database_name="d"))
    assert a._conn_key() != b._conn_key()


def test_mysql_adapter_reuses_connection_without_driver(monkeypatch):
    """MySQL 适配器只读路径应走连接池（驱动用假对象替换，验证握手只发生一次）。"""
    from app.adapters.mysql_adapter import MySQLAdapter

    pool = ConnectionPool(max_size=8, idle_ttl=300.0)
    monkeypatch.setattr("app.adapters.base.DB_POOL", pool, raising=False)

    made = []

    def fake_connect(self):
        conn = FakeConn(f"mysql-{len(made)}")
        conn.cursor = lambda: FakeCursor(conn)
        made.append(conn)
        return conn

    monkeypatch.setattr(MySQLAdapter, "connect", fake_connect)
    adapter = MySQLAdapter(ConnectionInfo(db_type="mysql", host="h", database_name="d"))
    assert adapter._query("SELECT 1") == [{"ok": 1}]
    assert adapter._query("SELECT 2") == [{"ok": 1}]
    assert len(made) == 1
    assert made[0].rolled_back == 2, "每次归还前都应回滚隐式事务（两次查询各一次）"


def test_mysql_query_error_discards_connection(monkeypatch):
    from app.adapters.mysql_adapter import MySQLAdapter

    pool = ConnectionPool(max_size=8, idle_ttl=300.0)
    monkeypatch.setattr("app.adapters.base.DB_POOL", pool, raising=False)

    state = {"fail": True}
    made = []

    def fake_connect(self):
        conn = FakeConn(f"mysql-{len(made)}")
        made.append(conn)
        def execute(sql, params=None):
            if state["fail"]:
                raise RuntimeError("bad sql")
        cur = FakeCursor(conn)
        cur.execute = execute
        conn.cursor = lambda: cur
        return conn

    monkeypatch.setattr(MySQLAdapter, "connect", fake_connect)
    adapter = MySQLAdapter(ConnectionInfo(db_type="mysql", host="h", database_name="d"))
    with pytest.raises(AdapterError):
        adapter._query("SELECT bad")
    assert pool.stats()["idle"] == 0
    assert made[0].closed is True


def test_drop_closes_only_that_bucket():
    pool = ConnectionPool(max_size=4, idle_ttl=300.0)
    keep, dropped = FakeConn("keep"), FakeConn("dropped")
    pool.release(("k1",), keep, close=lambda c: c.close())
    pool.release(("k2",), dropped, close=lambda c: c.close())

    assert pool.drop(("k1",)) == 1
    assert keep.closed is True
    assert dropped.closed is False
    assert pool.stats()["idle"] == 1


def test_sweep_reclaims_only_expired_connections():
    pool = ConnectionPool(max_size=4, idle_ttl=0.05)
    fresh, stale = FakeConn("fresh"), FakeConn("stale")
    pool.release(("k",), stale, close=lambda c: c.close())
    time.sleep(0.06)
    pool.release(("k",), fresh, close=lambda c: c.close())

    assert pool.sweep() == 1
    assert stale.closed is True
    assert fresh.closed is False
    assert pool.stats()["idle"] == 1


def test_release_uses_default_close_without_callback():
    pool = ConnectionPool(max_size=2, idle_ttl=300.0)
    conn = FakeConn()
    pool.release(("k",), conn)  # 不传 close 时走默认 conn.close()
    assert pool.drop(("k",)) == 1
    assert conn.closed is True
