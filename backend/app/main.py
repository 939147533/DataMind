"""FastAPI 应用入口。"""
import asyncio
import ipaddress
import logging
import secrets
import time
from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException
from fastapi import Request as FastAPIRequest
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, Response
from fastapi.staticfiles import StaticFiles
from prometheus_client import CONTENT_TYPE_LATEST, Counter, Histogram, generate_latest
from sqlalchemy import select

from . import security
from .adapters.pool import DB_POOL, pool_sweeper
from .config import BACKEND_DIR, DEFAULT_USERNAME, METRICS_TOKEN
from .database import SessionLocal, init_db
from .models import Setting
from .response import http_exception_handler, validation_exception_handler
from .routers import agent, audit, auth, charts, connections, export, metadata, monitor, roles, saved, schedule, sql, system, users
from .seed import admin_uses_default_password, seed_all
from .services import audit_service, schedule_service, sql_service
from .services.connection_service import repair_stored_paths
from .services.ssh_tunnel import close_all

FRONTEND_DIST = BACKEND_DIR.parent / "frontend" / "dist"

logger = logging.getLogger(__name__)

REQUEST_COUNT = Counter("http_requests_total", "HTTP 请求总数", ["method", "path", "status"])
REQUEST_LATENCY = Histogram("http_request_duration_seconds", "HTTP 请求耗时", ["method", "path"])


@asynccontextmanager
async def lifespan(app: FastAPI):
    await init_db()
    async with SessionLocal() as db:
        await seed_all(db)
        await repair_stored_paths(db)
        # 审计日志保留策略（默认 180 天）
        setting = (await db.execute(select(Setting).where(Setting.key == "audit_retention_days"))).scalar_one_or_none()
        days = 180
        try:
            days = int(setting.value) if setting and setting.value else 180
        except ValueError:
            days = 180
        await audit_service.cleanup_old_logs(db, days)
        # 超时未确认的写操作记录（默认 5 分钟）
        await sql_service.cleanup_expired_executions(db)
        if await admin_uses_default_password(db):
            logger.warning(
                "管理员 %s 仍在使用初始口令，请立即修改（或用 DBAGENT_ADMIN_PASSWORD 指定初始口令）",
                DEFAULT_USERNAME,
            )
    security.warm_up()  # 提前加载/生成加密密钥，让密钥问题在启动日志里就暴露
    if not METRICS_TOKEN:
        logger.warning(
            "/metrics 未配置 DBAGENT_METRICS_TOKEN：当前只允许本机/内网访问，公网部署请务必配置令牌"
        )
    scheduler = asyncio.create_task(schedule_service.scheduler_loop())
    sweeper = asyncio.create_task(pool_sweeper())
    yield
    scheduler.cancel()
    sweeper.cancel()
    close_all()
    DB_POOL.clear()


app = FastAPI(title="数据库 Agent Web 应用", version="2.0.0", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.add_exception_handler(HTTPException, http_exception_handler)
app.add_exception_handler(RequestValidationError, validation_exception_handler)


@app.middleware("http")
async def metrics_middleware(request, call_next):
    start = time.perf_counter()
    response = await call_next(request)
    duration = time.perf_counter() - start
    # 用路由模板而不是原始 URL 做标签：/api/connections/1 与 /2 收敛到同一标签，避免基数爆炸
    route = request.scope.get("route")
    path = getattr(route, "path", None) or "unmatched"
    REQUEST_COUNT.labels(method=request.method, path=path, status=str(response.status_code)).inc()
    REQUEST_LATENCY.labels(method=request.method, path=path).observe(duration)
    return response


app.include_router(auth.router)
app.include_router(connections.router)
app.include_router(sql.router)
app.include_router(metadata.router)
app.include_router(agent.router)
app.include_router(export.router)
app.include_router(charts.router)
app.include_router(system.router)
app.include_router(audit.router)
app.include_router(users.router)
app.include_router(roles.router)
app.include_router(monitor.router)
app.include_router(saved.router)
app.include_router(schedule.router)


@app.get("/api/health")
async def health():
    return {"code": 0, "message": "success", "data": {"status": "ok"}}


def _metrics_allowed(request: FastAPIRequest) -> bool:
    """指标鉴权：配了 DBAGENT_METRICS_TOKEN 就强制校验，未配置时只允许本机/内网访问。"""
    if METRICS_TOKEN:
        supplied = request.headers.get("authorization", "")
        if supplied.lower().startswith("bearer "):
            supplied = supplied[7:].strip()
        supplied = supplied or request.query_params.get("token", "")
        return secrets.compare_digest(supplied, METRICS_TOKEN)
    host = request.client.host if request.client else ""
    try:
        ip = ipaddress.ip_address(host)
    except ValueError:
        return False
    return ip.is_loopback or ip.is_private


@app.get("/metrics", include_in_schema=False)
async def metrics(request: FastAPIRequest):
    if not _metrics_allowed(request):
        raise HTTPException(status_code=401, detail="未授权的指标访问（请设置 DBAGENT_METRICS_TOKEN 并携带 Bearer 令牌）")
    return Response(content=generate_latest(), media_type=CONTENT_TYPE_LATEST)


if FRONTEND_DIST.exists():
    app.mount("/assets", StaticFiles(directory=FRONTEND_DIST / "assets"), name="assets")

    @app.get("/{full_path:path}", include_in_schema=False)
    async def spa(full_path: str):
        if full_path.startswith("api/"):
            raise HTTPException(status_code=404, detail="接口不存在")
        index = FRONTEND_DIST / "index.html"
        if index.exists():
            return FileResponse(index)
        raise HTTPException(status_code=404, detail="前端未构建")
