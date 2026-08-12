"""用户管理路由：用户增删改查、重置密码。"""
from fastapi import APIRouter, Depends, HTTPException, Query, Request
from sqlalchemy import or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from ..database import get_db
from ..deps import get_client_ip
from ..models import AuditLog, Role, User
from ..permissions import require_permission
from ..response import ok, page_data
from ..schemas import UserCreate, UserResetPassword, UserUpdate
from ..security import hash_password

router = APIRouter(prefix="/api/users", tags=["用户管理"])

DEFAULT_PASSWORD = "123456"


async def _role_names(db: AsyncSession) -> dict:
    rows = (await db.execute(select(Role))).scalars().all()
    return {r.code: r.name for r in rows}


def _user_out(user: User, role_names: dict | None = None) -> dict:
    return {
        "id": user.id,
        "username": user.username,
        "display_name": user.display_name,
        "role": user.role,
        "role_name": (role_names or {}).get(user.role, user.role),
        "is_active": user.is_active,
        "created_at": user.created_at.isoformat() if user.created_at else None,
        "last_login": user.last_login.isoformat() if user.last_login else None,
    }


async def _log(db: AsyncSession, actor: User, action: str, detail: str, request: Request) -> None:
    db.add(
        AuditLog(
            user_id=actor.id,
            action_type="user_manage",
            sql_text=detail[:4000],
            operation_type=action,
            status="success",
            client_ip=get_client_ip(request),
        )
    )
    await db.commit()


async def _active_admin_count(db: AsyncSession) -> int:
    rows = (
        await db.execute(select(User).where(User.role == "admin", User.is_active.is_(True)))
    ).scalars().all()
    return len(rows)


async def _ensure_role_exists(db: AsyncSession, role_code: str) -> None:
    if role_code == "admin":
        return
    role = (await db.execute(select(Role).where(Role.code == role_code))).scalar_one_or_none()
    if role is None:
        raise HTTPException(status_code=400, detail="角色不存在: " + role_code)


@router.get("")
async def list_users(
    search: str = "",
    role: str = "",
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
    user: User = Depends(require_permission("users")),
):
    query = select(User)
    if search:
        kw = "%" + search + "%"
        query = query.where(or_(User.username.like(kw), User.display_name.like(kw)))
    if role:
        query = query.where(User.role == role)
    total = len((await db.execute(query)).scalars().all())
    rows = (
        await db.execute(query.order_by(User.id.asc()).offset((page - 1) * page_size).limit(page_size))
    ).scalars().all()
    role_names = await _role_names(db)
    return ok(page_data([_user_out(u, role_names) for u in rows], total, page, page_size))


@router.get("/{user_id}")
async def get_user(user_id: int, db: AsyncSession = Depends(get_db), user: User = Depends(require_permission("users"))):
    target = (await db.execute(select(User).where(User.id == user_id))).scalar_one_or_none()
    if target is None:
        raise HTTPException(status_code=404, detail="用户不存在")
    return ok(_user_out(target, await _role_names(db)))


@router.post("")
async def create_user(
    data: UserCreate,
    request: Request,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(require_permission("users")),
):
    username = data.username.strip()
    if not username:
        raise HTTPException(status_code=400, detail="用户名不能为空")
    exists = (await db.execute(select(User).where(User.username == username))).scalar_one_or_none()
    if exists:
        raise HTTPException(status_code=400, detail="用户名已存在")
    role_code = data.role or "tech_query"
    await _ensure_role_exists(db, role_code)
    password = data.password or DEFAULT_PASSWORD
    if len(password) < 4:
        raise HTTPException(status_code=400, detail="密码长度至少 4 位")
    target = User(
        username=username,
        password_hash=hash_password(password),
        display_name=data.display_name or username,
        role=role_code,
        is_active=data.is_active,
    )
    db.add(target)
    await db.commit()
    await db.refresh(target)
    await _log(db, user, "create", "创建用户 " + username + "（角色: " + role_code + "）", request)
    return ok(_user_out(target, await _role_names(db)), "创建成功")


@router.put("/{user_id}")
async def update_user(
    user_id: int,
    data: UserUpdate,
    request: Request,
    db: AsyncSession = Depends(get_db),
    actor: User = Depends(require_permission("users")),
):
    target = (await db.execute(select(User).where(User.id == user_id))).scalar_one_or_none()
    if target is None:
        raise HTTPException(status_code=404, detail="用户不存在")
    payload = data.model_dump(exclude_unset=True)
    if "role" in payload and payload["role"] is not None:
        await _ensure_role_exists(db, payload["role"])
    if "password" in payload and payload["password"]:
        if len(payload["password"]) < 4:
            raise HTTPException(status_code=400, detail="密码长度至少 4 位")
        target.password_hash = hash_password(payload["password"])
    if "display_name" in payload and payload["display_name"] is not None:
        target.display_name = payload["display_name"]
    if "is_active" in payload:
        if target.id == actor.id and payload["is_active"] is False:
            raise HTTPException(status_code=400, detail="不能禁用当前登录用户")
        if payload["is_active"] is False and target.role == "admin" and target.is_active:
            if await _active_admin_count(db) <= 1:
                raise HTTPException(status_code=400, detail="不能禁用最后一个启用的管理员")
        target.is_active = payload["is_active"]
    if "role" in payload and payload["role"] is not None and payload["role"] != target.role:
        if target.role == "admin" and target.is_active:
            if await _active_admin_count(db) <= 1 and target.id == actor.id:
                raise HTTPException(status_code=400, detail="不能移除最后一个管理员的角色")
        target.role = payload["role"]
    await db.commit()
    await db.refresh(target)
    await _log(db, actor, "update", "更新用户 " + target.username, request)
    return ok(_user_out(target, await _role_names(db)), "更新成功")


@router.delete("/{user_id}")
async def delete_user(
    user_id: int,
    request: Request,
    db: AsyncSession = Depends(get_db),
    actor: User = Depends(require_permission("users")),
):
    target = (await db.execute(select(User).where(User.id == user_id))).scalar_one_or_none()
    if target is None:
        raise HTTPException(status_code=404, detail="用户不存在")
    if target.id == actor.id:
        raise HTTPException(status_code=400, detail="不能删除当前登录用户")
    if target.role == "admin" and target.is_active and await _active_admin_count(db) <= 1:
        raise HTTPException(status_code=400, detail="不能删除最后一个启用的管理员")
    username = target.username
    await db.delete(target)
    await db.commit()
    await _log(db, actor, "delete", "删除用户 " + username, request)
    return ok(message="删除成功")


@router.post("/{user_id}/reset-password")
async def reset_password(
    user_id: int,
    data: UserResetPassword,
    request: Request,
    db: AsyncSession = Depends(get_db),
    actor: User = Depends(require_permission("users")),
):
    target = (await db.execute(select(User).where(User.id == user_id))).scalar_one_or_none()
    if target is None:
        raise HTTPException(status_code=404, detail="用户不存在")
    password = data.password or DEFAULT_PASSWORD
    if len(password) < 4:
        raise HTTPException(status_code=400, detail="密码长度至少 4 位")
    target.password_hash = hash_password(password)
    await db.commit()
    await _log(db, actor, "reset_password", "重置用户 " + target.username + " 密码", request)
    return ok(message="密码已重置")
