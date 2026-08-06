"""FastAPI 依赖：数据库会话、当前用户、客户端 IP。"""
from datetime import datetime

from fastapi import Depends, HTTPException, Request
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from .database import get_db
from .models import Session as SessionModel
from .models import User

SESSION_COOKIE = "session_token"


async def get_current_user(request: Request, db: AsyncSession = Depends(get_db)) -> User:
    token = request.cookies.get(SESSION_COOKIE)
    if not token:
        raise HTTPException(status_code=401, detail="未登录")
    session = (await db.execute(select(SessionModel).where(SessionModel.token == token))).scalar_one_or_none()
    if not session:
        raise HTTPException(status_code=401, detail="会话已过期，请重新登录")
    if session.expires_at < datetime.now():
        await db.delete(session)
        await db.commit()
        raise HTTPException(status_code=401, detail="会话已过期，请重新登录")
    user = (await db.execute(select(User).where(User.id == session.user_id))).scalar_one_or_none()
    if not user or not user.is_active:
        raise HTTPException(status_code=401, detail="用户不存在或已禁用")
    return user


def get_client_ip(request: Request) -> str:
    xff = request.headers.get("x-forwarded-for")
    if xff:
        return xff.split(",")[0].strip()
    return request.client.host if request.client else ""
