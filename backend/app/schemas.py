"""Pydantic 请求/响应 Schema。"""
from datetime import datetime
from typing import Any, Optional

from pydantic import BaseModel, ConfigDict, Field


class ORMModel(BaseModel):
    model_config = ConfigDict(from_attributes=True)


# ---------- 认证 ----------
class LoginRequest(BaseModel):
    username: str
    password: str


# ---------- 连接管理 ----------
class ConnectionBase(BaseModel):
    name: str
    db_type: str = "sqlite"
    host: str = ""
    port: Optional[int] = None
    username: str = ""
    password: str = ""
    database_name: str = ""
    ssh_enabled: bool = False
    ssh_host: str = ""
    ssh_port: int = 22
    ssh_user: str = ""
    ssh_auth_type: str = "password"
    ssh_private_key: str = ""
    environment: str = "dev"
    description: str = ""


class ConnectionCreate(ConnectionBase):
    pass


class ConnectionUpdate(ConnectionBase):
    pass


class ConnectionOut(BaseModel):
    id: int
    name: str
    db_type: str
    host: str = ""
    port: Optional[int] = None
    username: str = ""
    has_password: bool = False
    database_name: str = ""
    ssh_enabled: bool = False
    ssh_host: str = ""
    ssh_port: int = 22
    ssh_user: str = ""
    ssh_auth_type: str = "password"
    environment: str = "dev"
    status: str = "unknown"
    description: str = ""
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None


class TestConnectionRequest(BaseModel):
    name: str = ""
    db_type: str = "sqlite"
    host: str = ""
    port: Optional[int] = None
    username: str = ""
    password: str = ""
    database_name: str = ""
    ssh_enabled: bool = False
    ssh_host: str = ""
    ssh_port: int = 22
    ssh_user: str = ""
    ssh_auth_type: str = "password"
    ssh_private_key: str = ""


# ---------- SQL 执行 ----------
class SqlExecuteRequest(BaseModel):
    datasource_id: int
    sql: str
    page: int = 1
    page_size: int = 100
    max_rows: int = 1000


class SqlConfirmRequest(BaseModel):
    execution_id: str
    confirmed: bool = True


class SqlFormatRequest(BaseModel):
    sql: str


# ---------- 元数据 ----------
class AlterTableRequest(BaseModel):
    schema_name: str = ""
    changes: str = Field(default="", description="变更描述或 DDL")
    ddl: str = ""


class FavoriteRequest(BaseModel):
    schema_name: str = ""
    table_name: str


# ---------- Agent ----------
class AgentSessionCreate(BaseModel):
    datasource_id: Optional[int] = None
    model_config_id: Optional[int] = None
    title: str = "新对话"


class AgentChatRequest(BaseModel):
    session_id: Optional[int] = None
    datasource_id: Optional[int] = None
    model_config_id: Optional[int] = None
    message: str


class AgentConfirmRequest(BaseModel):
    execution_id: str
    confirmed: bool = True


class ExplainRequest(BaseModel):
    datasource_id: Optional[int] = None
    sql: str


# ---------- AI 配置 ----------
class AIConfigCreate(BaseModel):
    provider: str
    api_key: str = ""
    api_base: str = ""
    model_name: str = ""
    max_tokens: int = 4096
    temperature: float = 0.7
    is_active: bool = True
    is_default: bool = False


class AIConfigUpdate(BaseModel):
    provider: Optional[str] = None
    api_key: Optional[str] = None
    api_base: Optional[str] = None
    model_name: Optional[str] = None
    max_tokens: Optional[int] = None
    temperature: Optional[float] = None
    is_active: Optional[bool] = None
    is_default: Optional[bool] = None


class AIConfigOut(BaseModel):
    id: int
    provider: str
    has_key: bool = False
    api_base: str = ""
    model_name: str = ""
    max_tokens: int = 4096
    temperature: float = 0.7
    is_active: bool = True
    is_default: bool = False


# ---------- 导出 ----------
class ExportResultRequest(BaseModel):
    datasource_id: int
    sql: str
    format: str = "csv"
    sheet_name: str = "结果"


class ExportDatabaseRequest(BaseModel):
    datasource_id: int
    tables: Optional[list] = None
    format: str = "word"
    include_ddl: bool = True


# ---------- 图表/仪表盘 ----------
class ChartCreate(BaseModel):
    name: str
    datasource_id: Optional[int] = None
    sql_text: str = ""
    chart_type: str = "bar"
    x_column: str = ""
    y_column: str = ""
    aggregation: str = "none"
    options: str = "{}"


class ChartUpdate(BaseModel):
    name: Optional[str] = None
    datasource_id: Optional[int] = None
    sql_text: Optional[str] = None
    chart_type: Optional[str] = None
    x_column: Optional[str] = None
    y_column: Optional[str] = None
    aggregation: Optional[str] = None
    options: Optional[str] = None


class DashboardCreate(BaseModel):
    name: str
    chart_ids: list = []
    layout: str = "{}"


class DashboardUpdate(BaseModel):
    name: Optional[str] = None
    chart_ids: Optional[list] = None
    layout: Optional[str] = None
    is_public: Optional[bool] = None


# ---------- 设置 ----------
class SettingsUpdate(BaseModel):
    values: dict[str, Any] = Field(default_factory=dict)


# ---------- 审计 ----------
class AuditLogOut(ORMModel):
    id: int
    user_id: Optional[int] = None
    action_type: str = ""
    sql_text: str = ""
    operation_type: str = ""
    datasource_id: Optional[int] = None
    status: str = ""
    client_ip: str = ""
    created_at: Optional[datetime] = None

# ---------- 用户管理 ----------
class UserCreate(BaseModel):
    username: str
    password: str = "123456"
    display_name: str = ""
    role: str = "tech_query"
    is_active: bool = True


class UserUpdate(BaseModel):
    display_name: Optional[str] = None
    password: Optional[str] = None
    role: Optional[str] = None
    is_active: Optional[bool] = None


class UserResetPassword(BaseModel):
    password: str = "123456"


# ---------- 角色管理 ----------
class RoleCreate(BaseModel):
    code: str
    name: str
    description: str = ""
    permissions: list = []


class RoleUpdate(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None
    permissions: Optional[list] = None


class RoleUsersUpdate(BaseModel):
    user_ids: list[int] = []
