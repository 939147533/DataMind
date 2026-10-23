"""认证路由：登录/登出/当前用户。"""
from datetime import datetime, timedelta

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import JSONResponse
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ..config import COOKIE_SECURE, SESSION_TTL_SECONDS
from ..database import get_db
from ..deps import SESSION_COOKIE, get_client_ip, get_current_user
from ..models import Session as SessionModel
from ..models import User
from ..permissions import get_user_permissions
from ..response import ok
from ..schemas import LoginRequest
from ..security import generate_token, verify_password
from ..services.audit_service import record_audit

router = APIRouter(prefix="/api/auth", tags=["认证"])


def _user_dict(user: User, permissions: list | None = None) -> dict:
    return {
        "id": user.id,
        "username": user.username,
        "display_name": user.display_name,
        "role": user.role,
        "last_login": user.last_login.isoformat() if user.last_login else None,
        "permissions": permissions or [],
    }


@router.post("/login")
async def login(data: LoginRequest, request: Request, db: AsyncSession = Depends(get_db)):
    user = (await db.execute(select(User).where(User.username == data.username))).scalar_one_or_none()
    if user is None or not verify_password(data.password, user.password_hash):
        raise HTTPException(status_code=401, detail="用户名或密码错误")
    if not user.is_active:
        raise HTTPException(status_code=403, detail="用户已被禁用")
    token = generate_token()
    db.add(
        SessionModel(
            token=token,
            user_id=user.id,
            expires_at=datetime.now() + timedelta(seconds=SESSION_TTL_SECONDS),
        )
    )
    user.last_login = datetime.now()
    await db.commit()
    perms = await get_user_permissions(db, user)
    await record_audit(db, user.id, "login", "", "", None, "success", get_client_ip(request))
    # 响应体不回传 session token：前端全程依赖 HttpOnly Cookie，token 一旦进入 JS 可读的
    # 响应体，HttpOnly 的保护就形同虚设（XSS 或记录响应体的中间层都能拿到会话）。
    response = JSONResponse(content=ok({"user": _user_dict(user, sorted(perms))}, "登录成功"))
    response.set_cookie(
        SESSION_COOKIE,
        token,
        httponly=True,
        max_age=SESSION_TTL_SECONDS,
        samesite="lax",
        secure=COOKIE_SECURE,
    )
    return response


@router.post("/logout")
async def logout(request: Request, db: AsyncSession = Depends(get_db)):
    token = request.cookies.get(SESSION_COOKIE)
    if token:
        session = (await db.execute(select(SessionModel).where(SessionModel.token == token))).scalar_one_or_none()
        if session:
            await db.delete(session)
            await db.commit()
    response = JSONResponse(content=ok(message="已登出"))
    response.delete_cookie(SESSION_COOKIE)
    return response


@router.get("/me")
async def me(user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    perms = await get_user_permissions(db, user)
    return ok(_user_dict(user, sorted(perms)))
