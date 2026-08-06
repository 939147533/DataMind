"""AI Agent 路由：会话、SSE 对话、解释、优化。"""
import asyncio
import json

from fastapi import APIRouter, Depends, Request
from fastapi.responses import StreamingResponse
from sqlalchemy.ext.asyncio import AsyncSession

from ..database import get_db
from ..deps import get_client_ip, get_current_user
from ..models import User
from ..response import ok
from ..schemas import AgentChatRequest, AgentConfirmRequest, AgentSessionCreate, ExplainRequest
from ..services import agent_service

router = APIRouter(prefix="/api/agent", tags=["AI Agent"])


def sse(gen):
    async def event_stream():
        try:
            async for event in gen:
                yield f"data: {json.dumps(event, ensure_ascii=False)}\n\n"
        except asyncio.CancelledError:
            raise

    return StreamingResponse(event_stream(), media_type="text/event-stream")


@router.post("/sessions")
async def create_session(data: AgentSessionCreate, db: AsyncSession = Depends(get_db), user: User = Depends(get_current_user)):
    session = await agent_service.create_session(db, data.datasource_id, data.model_config_id, data.title)
    return ok({"id": session.id, "title": session.title, "datasource_id": session.datasource_id, "model_config_id": session.model_config_id})


@router.get("/sessions")
async def list_sessions(db: AsyncSession = Depends(get_db), user: User = Depends(get_current_user)):
    return ok(await agent_service.list_sessions(db))


@router.delete("/sessions/{session_id}")
async def delete_session(session_id: int, db: AsyncSession = Depends(get_db), user: User = Depends(get_current_user)):
    await agent_service.delete_session(db, session_id)
    return ok(message="已删除")


@router.get("/sessions/{session_id}/messages")
async def session_messages(session_id: int, db: AsyncSession = Depends(get_db), user: User = Depends(get_current_user)):
    return ok(await agent_service.list_messages(db, session_id))


@router.post("/chat")
async def chat(data: AgentChatRequest, request: Request, db: AsyncSession = Depends(get_db), user: User = Depends(get_current_user)):
    gen = agent_service.agent_chat(
        db,
        data.session_id,
        data.datasource_id,
        data.model_config_id,
        data.message,
        user.id,
        get_client_ip(request),
    )
    return sse(gen)


@router.post("/confirm")
async def confirm(data: AgentConfirmRequest, request: Request, db: AsyncSession = Depends(get_db), user: User = Depends(get_current_user)):
    result = await agent_service.agent_confirm(db, data.execution_id, data.confirmed, get_client_ip(request))
    return ok(result)


@router.post("/explain")
async def explain(data: ExplainRequest, request: Request, db: AsyncSession = Depends(get_db), user: User = Depends(get_current_user)):
    return sse(agent_service.explain_sql(db, data.datasource_id, data.sql, user.id))


@router.post("/optimize")
async def optimize(data: ExplainRequest, request: Request, db: AsyncSession = Depends(get_db), user: User = Depends(get_current_user)):
    return sse(agent_service.optimize_sql(db, data.datasource_id, data.sql, user.id))
