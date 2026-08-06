"""SSH 隧道管理（基于 sshtunnel，P1）。"""
import threading

from ..adapters.base import AdapterError, ConnectionInfo

_tunnels: dict = {}
_lock = threading.Lock()


def _key(conn: ConnectionInfo) -> str:
    return f"{conn.ssh_user}@{conn.ssh_host}:{conn.ssh_port or 22}->{conn.host}:{conn.port or 3306}"


def get_local_port(conn: ConnectionInfo) -> int | None:
    if not conn.ssh_enabled:
        return None
    try:
        from sshtunnel import SSHTunnelForwarder
    except ImportError as exc:
        raise AdapterError("未安装 sshtunnel/paramiko，无法使用 SSH 隧道") from exc
    key = _key(conn)
    with _lock:
        tunnel = _tunnels.get(key)
        if tunnel is not None and tunnel.is_active:
            return tunnel.local_bind_port
        try:
            ssh_password = conn.password if conn.ssh_auth_type == "password" else None
            ssh_pkey = None
            if conn.ssh_auth_type == "key" and conn.ssh_private_key:
                from io import StringIO

                import paramiko

                ssh_pkey = paramiko.RSAKey.from_private_key(StringIO(conn.ssh_private_key))
            tunnel = SSHTunnelForwarder(
                (conn.ssh_host, conn.ssh_port or 22),
                ssh_username=conn.ssh_user,
                ssh_password=ssh_password,
                ssh_pkey=ssh_pkey,
                remote_bind_address=(conn.host, conn.port or 3306),
            )
            tunnel.start()
            _tunnels[key] = tunnel
            return tunnel.local_bind_port
        except Exception as exc:  # noqa: BLE001
            raise AdapterError(f"SSH 隧道建立失败: {exc}") from exc


def close_all() -> None:
    with _lock:
        for tunnel in _tunnels.values():
            try:
                tunnel.stop()
            except Exception:  # noqa: BLE001
                pass
        _tunnels.clear()
