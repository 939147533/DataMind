"""FastAPI 应用入口。"""
import asyncio
import time
from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, Response
from fastapi.staticfiles import StaticFiles
from prometheus_client import CONTENT_TYPE_LATEST, Counter, Histogram, generate_latest
from sqlalchemy import select

from .config import BACKEND_DIR
from .database import SessionLocal, init_db
from .models import Setting
from .response import http_exception_handler, validation_exception_handler
from .routers import agent, audit, auth, charts, connections, export, metadata, monitor, roles, saved, schedule, sql, system, users
from .seed import seed_all
from .services import audit_service, schedule_service
from .services.connection_service import repair_stored_paths
from .services.ssh_tunnel import close_all

FRONTEND_DIST = BACKEND_DIR.parent / "frontend" / "dist"

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
    scheduler = asyncio.create_task(schedule_service.scheduler_loop())
    yield
    scheduler.cancel()
    close_all()


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
    path = request.url.path
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


@app.get("/metrics", include_in_schema=False)
async def metrics():
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
