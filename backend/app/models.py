"""SQLAlchemy 数据模型（对应需求文档第 5 章）。"""
from datetime import datetime

from sqlalchemy import Boolean, Column, DateTime, Float, ForeignKey, Integer, String, Text

from .database import Base


def now() -> datetime:
    return datetime.now()


class DataSource(Base):
    __tablename__ = "datasources"
    id = Column(Integer, primary_key=True, autoincrement=True)
    name = Column(String(100), unique=True, nullable=False)
    db_type = Column(String(30), nullable=False)
    host = Column(String(255), default="")
    port = Column(Integer, nullable=True)
    username = Column(String(100), default="")
    encrypted_password = Column(Text, default="")
    database_name = Column(String(100), default="")
    ssh_enabled = Column(Boolean, default=False)
    ssh_host = Column(String(255), default="")
    ssh_port = Column(Integer, default=22)
    ssh_user = Column(String(100), default="")
    ssh_auth_type = Column(String(20), default="password")
    ssh_private_key = Column(Text, default="")
    environment = Column(String(20), default="dev")
    status = Column(String(20), default="unknown")
    description = Column(Text, default="")
    created_at = Column(DateTime, default=now)
    updated_at = Column(DateTime, default=now, onupdate=now)


class User(Base):
    __tablename__ = "users"
    id = Column(Integer, primary_key=True, autoincrement=True)
    username = Column(String(50), unique=True, nullable=False)
    password_hash = Column(String(255), nullable=False)
    display_name = Column(String(100), default="")
    is_active = Column(Boolean, default=True)
    role = Column(String(20), default="user")
    created_at = Column(DateTime, default=now)
    last_login = Column(DateTime, nullable=True)


class AIConfig(Base):
    __tablename__ = "ai_configs"
    id = Column(Integer, primary_key=True, autoincrement=True)
    provider = Column(String(20), nullable=False)
    api_key = Column(Text, default="")
    api_base = Column(String(255), default="")
    model_name = Column(String(100), default="")
    max_tokens = Column(Integer, default=4096)
    temperature = Column(Float, default=0.7)
    is_active = Column(Boolean, default=True)
    is_default = Column(Boolean, default=False)
    created_at = Column(DateTime, default=now)
    updated_at = Column(DateTime, default=now, onupdate=now)


class JdbcDriver(Base):
    __tablename__ = "jdbc_drivers"
    id = Column(Integer, primary_key=True, autoincrement=True)
    db_type = Column(String(30), default="")
    driver_class = Column(String(200), default="")
    version = Column(String(20), default="")
    file_path = Column(String(500), default="")
    file_name = Column(String(255), default="")
    file_size = Column(Integer, default=0)
    upload_time = Column(DateTime, default=now)


class QueryHistory(Base):
    __tablename__ = "query_history"
    id = Column(Integer, primary_key=True, autoincrement=True)
    datasource_id = Column(Integer, ForeignKey("datasources.id"), nullable=True)
    sql_text = Column(Text, default="")
    status = Column(String(20), default="success")
    row_count = Column(Integer, default=0)
    duration_ms = Column(Integer, default=0)
    error_message = Column(Text, default="")
    created_at = Column(DateTime, default=now)


class AgentSession(Base):
    __tablename__ = "agent_sessions"
    id = Column(Integer, primary_key=True, autoincrement=True)
    title = Column(String(200), default="新对话")
    datasource_id = Column(Integer, ForeignKey("datasources.id"), nullable=True)
    model_config_id = Column(Integer, ForeignKey("ai_configs.id"), nullable=True)
    message_count = Column(Integer, default=0)
    created_at = Column(DateTime, default=now)
    updated_at = Column(DateTime, default=now, onupdate=now)


class AgentMessage(Base):
    __tablename__ = "agent_messages"
    id = Column(Integer, primary_key=True, autoincrement=True)
    session_id = Column(Integer, ForeignKey("agent_sessions.id"), nullable=False)
    role = Column(String(20), default="user")
    content = Column(Text, default="")
    message_type = Column(String(20), default="text")
    created_at = Column(DateTime, default=now)


class AuditLog(Base):
    __tablename__ = "audit_logs"
    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=True)
    action_type = Column(String(30), default="")
    sql_text = Column(Text, default="")
    operation_type = Column(String(20), default="")
    datasource_id = Column(Integer, nullable=True)
    status = Column(String(20), default="")
    client_ip = Column(String(45), default="")
    created_at = Column(DateTime, default=now)


class FavoritedTable(Base):
    __tablename__ = "favorited_tables"
    id = Column(Integer, primary_key=True, autoincrement=True)
    datasource_id = Column(Integer, ForeignKey("datasources.id"), nullable=False)
    schema_name = Column(String(100), default="")
    table_name = Column(String(100), nullable=False)
    created_at = Column(DateTime, default=now)


class Chart(Base):
    __tablename__ = "charts"
    id = Column(Integer, primary_key=True, autoincrement=True)
    name = Column(String(100), nullable=False)
    datasource_id = Column(Integer, ForeignKey("datasources.id"), nullable=True)
    sql_text = Column(Text, default="")
    chart_type = Column(String(20), default="bar")
    x_column = Column(String(100), default="")
    y_column = Column(String(100), default="")
    aggregation = Column(String(20), default="none")
    options = Column(Text, default="{}")
    created_at = Column(DateTime, default=now)
    updated_at = Column(DateTime, default=now, onupdate=now)


class Dashboard(Base):
    __tablename__ = "dashboards"
    id = Column(Integer, primary_key=True, autoincrement=True)
    name = Column(String(100), nullable=False)
    chart_ids = Column(Text, default="[]")
    layout = Column(Text, default="{}")
    is_public = Column(Boolean, default=False)
    share_token = Column(String(64), default="")
    created_at = Column(DateTime, default=now)
    updated_at = Column(DateTime, default=now, onupdate=now)


class Session(Base):
    __tablename__ = "sessions"
    token = Column(String(64), primary_key=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    created_at = Column(DateTime, default=now)
    expires_at = Column(DateTime, nullable=False)


class Setting(Base):
    __tablename__ = "settings"
    key = Column(String(100), primary_key=True)
    value = Column(Text, default="")
    updated_at = Column(DateTime, default=now, onupdate=now)
