"""目标库连接池：跨请求复用驱动连接，避免每次元数据查询都重新握手。

设计要点：
- 按连接参数（db_type/host/port/database/user/password）分桶，跨适配器实例共享；
  每个请求都会新建适配器，只有模块级池才能复用连接。
- 借出即独占，线程安全：所有调用都来自 `asyncio.to_thread` 的工作线程。
- 借出前做存活探测（驱动实现提供），失活或空闲超时的连接关闭后重建。
- 归还前执行 reset 回调（回滚驱动隐式开启的事务），失败则丢弃而不是污染池。
- 池内空闲连接数达到上限时，多余的连接直接关闭。

仅用于只读路径（元数据查询 / 采样）；写操作仍由 `execute()` 独占连接，保证事务语义清晰。
"""
import asyncio
import threading
import time

from .. import config


def _default_close(conn) -> None:
    """关闭连接，忽略驱动抛出的收尾异常。"""
    try:
        conn.close()
    except Exception:  # noqa: BLE001
        pass


class ConnectionPool:
    """按 key 分桶的轻量连接池。"""

    def __init__(self, max_size: int = 8, idle_ttl: float = 300.0):
        self.max_size = max(1, int(max_size))
        self.idle_ttl = max(0.0, float(idle_ttl))
        self._idle: dict[tuple, list[tuple[float, object]]] = {}
        self._lock = threading.Lock()
        self.created = 0
        self.reused = 0
        self.closed = 0

    def _pop(self, key: tuple):
        with self._lock:
            bucket = self._idle.get(key)
            if not bucket:
                return None
            created_at, conn = bucket.pop()
            if not bucket:
                self._idle.pop(key, None)
            return created_at, conn

    def _close_conn(self, conn, close) -> None:
        (close or _default_close)(conn)

    def acquire(self, key: tuple, factory, *, is_alive=None, close=None):
        """借出一个连接：优先复用空闲连接，失效/超时/探测失败则关闭后新建。"""
        while True:
            entry = self._pop(key)
            if entry is None:
                break
            created_at, conn = entry
            expired = bool(self.idle_ttl) and (time.monotonic() - created_at) > self.idle_ttl
            if expired or (is_alive is not None and not is_alive(conn)):
                self._close_conn(conn, close)
                with self._lock:
                    self.closed += 1
                continue
            with self._lock:
                self.reused += 1
            return conn
        with self._lock:
            self.created += 1
        return factory()

    def release(self, key: tuple, conn, *, broken: bool = False, reset=None, close=None) -> None:
        """归还连接：broken 或 reset 失败时丢弃，池满时多余连接直接关闭。"""
        if conn is None:
            return
        if broken:
            self._close_conn(conn, close)
            with self._lock:
                self.closed += 1
            return
        if reset is not None:
            try:
                reset(conn)
            except Exception:  # noqa: BLE001
                self._close_conn(conn, close)
                with self._lock:
                    self.closed += 1
                return
        with self._lock:
            bucket = self._idle.setdefault(key, [])
            if len(bucket) < self.max_size:
                bucket.append((time.monotonic(), conn))
                return
            self.closed += 1
        self._close_conn(conn, close)

    def stats(self) -> dict:
        with self._lock:
            return {
                "buckets": len(self._idle),
                "idle": sum(len(b) for b in self._idle.values()),
                "max_size": self.max_size,
                "idle_ttl": self.idle_ttl,
                "created": self.created,
                "reused": self.reused,
                "closed": self.closed,
            }

    def drop(self, key: tuple, close=None) -> int:
        """丢弃某个桶的全部空闲连接（数据源被改动或删除后调用），返回关闭数量。"""
        with self._lock:
            bucket = self._idle.pop(key, [])
            self.closed += len(bucket)
        for _, conn in bucket:
            self._close_conn(conn, close)
        return len(bucket)

    def sweep(self, close=None) -> int:
        """回收所有桶里空闲超时的连接（数据源删除、SSH 隧道换端口后残留）。"""
        if not self.idle_ttl:
            return 0
        now = time.monotonic()
        stale: list = []
        with self._lock:
            for key, bucket in list(self._idle.items()):
                keep = []
                for created_at, conn in bucket:
                    if (now - created_at) > self.idle_ttl:
                        stale.append(conn)
                    else:
                        keep.append((created_at, conn))
                if keep:
                    self._idle[key] = keep
                else:
                    self._idle.pop(key, None)
            self.closed += len(stale)
        for conn in stale:
            self._close_conn(conn, close)
        return len(stale)

    def clear(self, close=None) -> None:
        with self._lock:
            buckets = list(self._idle.values())
            self._idle.clear()
        for bucket in buckets:
            for _, conn in bucket:
                self._close_conn(conn, close)


DB_POOL = ConnectionPool(max_size=config.DB_POOL_SIZE, idle_ttl=config.DB_POOL_IDLE_TTL)


async def pool_sweeper(interval: float = 60.0) -> None:
    """后台回收空闲超时连接；由 lifespan 启动，进程退出时取消。"""
    while True:
        await asyncio.sleep(interval)
        try:
            DB_POOL.sweep()
        except Exception:  # noqa: BLE001
            pass
