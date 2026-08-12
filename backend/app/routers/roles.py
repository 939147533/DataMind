"""角色管理路由：角色 CRUD、功能权限配置、角色成员管理。"""
import json

from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ..database import get_db
from ..deps import get_client_ip
from ..models import AuditLog, Role, User
from ..permissions import PERMISSION_NAMES, require_permission
from ..response import ok
from ..schemas import RoleCreate, RoleUpdate, RoleUsersUpdate

router = APIRouter(prefix="/api/roles", tags=["角色管理"])


def _parse_permissions(role: Role) -> list:
    try:
        return json.loads(role.permissions or "[]")
    except Exception:
        return []


def _role_out(role: Role, user_count: int = 0) -> dict:
    return {
        "id": role.id,
        "code": role.code,
        "name": role.name,
        "description": role.description,
        "permissions": _parse_permissions(role),
        "is_builtin": role.is_builtin,
        "user_count": user_count,
    }


def _validate_permissions(perms: list) -> None:
    for p in perms or []:
        if p == "*":
            continue
        if p not in PERMISSION_NAMES:
            raise HTTPException(status_code=400, detail="无效的权限码: " + str(p))


async def _user_count(db: AsyncSession, role_code: str) -> int:
    rows = (await db.execute(select(User).where(User.role == role_code))).scalars().all()
    return len(rows)


async def _active_admin_count(db: AsyncSession) -> int:
    rows = (
        await db.execute(select(User).where(User.role == "admin", User.is_active.is_(True)))
    ).scalars().all()
    return len(rows)


async def _log(db: AsyncSession, actor: User, action: str, detail: str, request: Request) -> None:
    db.add(
        AuditLog(
            user_id=actor.id,
            action_type="role_manage",
            sql_text=detail[:4000],
            operation_type=action,
            status="success",
            client_ip=get_client_ip(request),
        )
    )
    await db.commit()


async def _get_role(db: AsyncSession, role_id: int) -> Role:
    role = (await db.execute(select(Role).where(Role.id == role_id))).scalar_one_or_none()
    if role is None:
        raise HTTPException(status_code=404, detail="角色不存在")
    return role


@router.get("")
async def list_roles(db: AsyncSession = Depends(get_db), user: User = Depends(require_permission("roles"))):
    rows = (await db.execute(select(Role).order_by(Role.id.asc()))).scalars().all()
    result = []
    for r in rows:
        result.append(_role_out(r, await _user_count(db, r.code)))
    return ok(result)


@router.get("/{role_id}")
async def get_role(role_id: int, db: AsyncSession = Depends(get_db), user: User = Depends(require_permission("roles"))):
    role = await _get_role(db, role_id)
    return ok(_role_out(role, await _user_count(db, role.code)))


@router.post("")
async def create_role(
    data: RoleCreate,
    request: Request,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(require_permission("roles")),
):
    code = data.code.strip()
    if not code:
        raise HTTPException(status_code=400, detail="角色编码不能为空")
    exists = (await db.execute(select(Role).where(Role.code == code))).scalar_one_or_none()
    if exists:
        raise HTTPException(status_code=400, detail="角色编码已存在")
    perms = data.permissions or []
    _validate_permissions(perms)
    role = Role(
        code=code,
        name=data.name or code,
        description=data.description,
        permissions=json.dumps(perms, ensure_ascii=False),
        is_builtin=False,
    )
    db.add(role)
    await db.commit()
    await db.refresh(role)
    await _log(db, user, "create", "创建角色 " + code + "（" + (data.name or code) + "）", request)
    return ok(_role_out(role, 0), "创建成功")


@router.put("/{role_id}")
async def update_role(
    role_id: int,
    data: RoleUpdate,
    request: Request,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(require_permission("roles")),
):
    role = await _get_role(db, role_id)
    payload = data.model_dump(exclude_unset=True)
    if "permissions" in payload and payload["permissions"] is not None:
        perms = payload["permissions"]
        if "*" in perms and role.code != "admin":
            raise HTTPException(status_code=400, detail="仅管理员角色可拥有全部权限")
        _validate_permissions(perms)
        role.permissions = json.dumps(perms, ensure_ascii=False)
    if role.is_builtin:
        if "code" in payload and payload["code"]:
            raise HTTPException(status_code=400, detail="内置角色编码不可修改")
        if "name" in payload and payload["name"] and payload["name"] != role.name:
            raise HTTPException(status_code=400, detail="内置角色名称不可修改")
    else:
        if "code" in payload and payload["code"]:
            new_code = payload["code"].strip()
            if not new_code:
                raise HTTPException(status_code=400, detail="角色编码不能为空")
            exists = (await db.execute(select(Role).where(Role.code == new_code))).scalar_one_or_none()
            if exists and exists.id != role.id:
                raise HTTPException(status_code=400, detail="角色编码已存在")
            role.code = new_code
        if "name" in payload and payload["name"]:
            role.name = payload["name"]
    if "description" in payload and payload["description"] is not None:
        role.description = payload["description"]
    await db.commit()
    await db.refresh(role)
    await _log(db, user, "update", "更新角色 " + role.code, request)
    return ok(_role_out(role, await _user_count(db, role.code)), "更新成功")


@router.delete("/{role_id}")
async def delete_role(
    role_id: int,
    request: Request,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(require_permission("roles")),
):
    role = await _get_role(db, role_id)
    if role.is_builtin:
        raise HTTPException(status_code=400, detail="内置角色不可删除")
    cnt = await _user_count(db, role.code)
    if cnt:
        raise HTTPException(status_code=400, detail="该角色下仍有 %d 个用户，请先调整用户角色" % cnt)
    code = role.code
    await db.delete(role)
    await db.commit()
    await _log(db, user, "delete", "删除角色 " + code, request)
    return ok(message="删除成功")


@router.get("/{role_id}/users")
async def role_users(role_id: int, db: AsyncSession = Depends(get_db), user: User = Depends(require_permission("roles"))):
    role = await _get_role(db, role_id)
    rows = (await db.execute(select(User).where(User.role == role.code).order_by(User.id.asc()))).scalars().all()
    return ok(
        [
            {
                "id": u.id,
                "username": u.username,
                "display_name": u.display_name,
                "is_active": u.is_active,
                "last_login": u.last_login.isoformat() if u.last_login else None,
            }
            for u in rows
        ]
    )


@router.put("/{role_id}/users")
async def set_role_users(
    role_id: int,
    data: RoleUsersUpdate,
    request: Request,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(require_permission("roles")),
):
    role = await _get_role(db, role_id)
    user_ids = list(dict.fromkeys(data.user_ids or []))
    if user_ids:
        users = (await db.execute(select(User).where(User.id.in_(user_ids)))).scalars().all()
        if len(users) != len(user_ids):
            raise HTTPException(status_code=400, detail="包含不存在的用户")
    else:
        users = []
    if role.code != "admin":
        for u in users:
            if u.role == "admin" and u.is_active and await _active_admin_count(db) <= 1:
                raise HTTPException(status_code=400, detail="不能移除最后一个启用的管理员")
    for u in users:
        u.role = role.code
    await db.commit()
    await _log(db, user, "assign", "为角色 " + role.name + " 分配用户 %d 个" % len(users), request)
    return ok(message="已为角色 " + role.name + " 分配 %d 个用户" % len(users))
