"""权限模型：功能权限常量、内置角色、权限解析与依赖。"""
import json

from fastapi import Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from .database import get_db
from .deps import get_current_user
from .models import Role, User

# 功能权限码
PERMISSIONS = [
    {"code": "workspace", "name": "SQL 工作台", "group": "工作台", "description": "访问 SQL 工作台并执行只读查询"},
    {"code": "ai_query", "name": "智能查询", "group": "工作台", "description": "自然语言查询数据、导出结果、生成图表"},
    {"code": "sql_write", "name": "写操作 (DML)", "group": "工作台", "description": "执行 INSERT/UPDATE/DELETE 等写操作"},
    {"code": "sql_ddl", "name": "结构变更 (DDL)", "group": "工作台", "description": "执行 CREATE/ALTER/DROP 等结构变更"},
    {"code": "agent", "name": "AI Agent", "group": "工作台", "description": "使用 AI 智能助手"},
    {"code": "connections", "name": "连接管理-查看", "group": "连接", "description": "查看数据源连接、测试连接"},
    {"code": "connections_manage", "name": "连接管理-维护", "group": "连接", "description": "新增/编辑/删除数据源连接"},
    {"code": "reports", "name": "报表-查看", "group": "报表", "description": "查看图表与仪表盘"},
    {"code": "reports_manage", "name": "报表-维护", "group": "报表", "description": "新增/编辑/删除图表与仪表盘"},
    {"code": "settings", "name": "系统设置", "group": "系统", "description": "AI 配置、JDBC 驱动、偏好设置"},
    {"code": "audit", "name": "审计日志", "group": "系统", "description": "查看操作审计日志"},
    {"code": "users", "name": "用户管理", "group": "系统", "description": "管理用户账号"},
    {"code": "roles", "name": "角色管理", "group": "系统", "description": "管理角色与功能权限"},
]
PERMISSION_NAMES = {p["code"]: p["name"] for p in PERMISSIONS}

# 内置角色（固定 5 个）
BUILTIN_ROLES = [
    {
        "code": "admin",
        "name": "管理员",
        "description": "系统内置角色：拥有全部功能权限",
        "permissions": ["*"],
    },
    {
        "code": "tech_manager",
        "name": "技术管理",
        "description": "技术类功能全面管理：SQL 工作台（含写操作与结构变更）、连接、报表、系统设置、审计",
        "permissions": ["workspace", "ai_query", "sql_write", "sql_ddl", "agent", "connections", "connections_manage", "reports", "reports_manage", "settings", "audit"],
    },
    {
        "code": "tech_query",
        "name": "技术查询",
        "description": "技术类查询：SQL 工作台（含写操作，禁止结构变更）、AI Agent、连接查看、报表查看、审计",
        "permissions": ["workspace", "ai_query", "sql_write", "agent", "connections", "reports", "audit"],
    },
    {
        "code": "biz_manager",
        "name": "业务管理",
        "description": "业务类管理：报表维护、SQL 只读查询、连接查看、审计",
        "permissions": ["workspace", "ai_query", "connections", "reports", "reports_manage", "audit"],
    },
    {
        "code": "biz_query",
        "name": "业务查询",
        "description": "业务类查询：报表查看、SQL 只读查询、连接查看",
        "permissions": ["workspace", "ai_query", "connections", "reports"],
    },
]

# SQL 操作类型 -> 所需权限
OP_TO_PERMISSION = {"READ": "workspace", "DML": "sql_write", "DDL": "sql_ddl"}


async def get_user_permissions(db: AsyncSession, user: User) -> set:
    if user.role == "admin":
        return {"*"}
    role = (await db.execute(select(Role).where(Role.code == user.role))).scalar_one_or_none()
    if role is None:
        return set()
    try:
        perms = json.loads(role.permissions or "[]")
    except Exception:
        perms = []
    return set(perms or [])


async def check_permission(db: AsyncSession, user: User, feature: str) -> None:
    perms = await get_user_permissions(db, user)
    if "*" in perms or feature in perms:
        return
    raise HTTPException(status_code=403, detail="无权限执行该操作")


def require_permission(feature: str):
    async def _checker(db: AsyncSession = Depends(get_db), user: User = Depends(get_current_user)):
        await check_permission(db, user, feature)
        return user

    return _checker


def require_any_permission(*features: str):
    async def _checker(db: AsyncSession = Depends(get_db), user: User = Depends(get_current_user)):
        await check_any_permission(db, user, features)
        return user

    return _checker


async def check_any_permission(db: AsyncSession, user, features) -> None:
    perms = await get_user_permissions(db, user)
    if "*" in perms or any(f in perms for f in features):
        return
    raise HTTPException(status_code=403, detail="无权限执行该操作")


async def check_sql_permission(db: AsyncSession, user_id, op_type: str) -> None:
    if not user_id:
        return
    user = (await db.execute(select(User).where(User.id == user_id))).scalar_one_or_none()
    if user is None:
        raise HTTPException(status_code=401, detail="用户不存在")
    if op_type == "READ":
        await check_any_permission(db, user, ("workspace", "ai_query"))
        return
    await check_permission(db, user, OP_TO_PERMISSION.get(op_type, "workspace"))
