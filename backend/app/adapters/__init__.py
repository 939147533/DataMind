"""数据库适配层。"""
from .base import AdapterError, ConnectionInfo
from .registry import get_adapter, test_connection

__all__ = ["AdapterError", "ConnectionInfo", "get_adapter", "test_connection"]
