"""测试夹具：独立数据目录 + 已登录客户端。"""
import os
import tempfile

_TMP = tempfile.mkdtemp(prefix="dbagent_test_")
os.environ["DBAGENT_DATA_DIR"] = _TMP

import pytest_asyncio  # noqa: E402
from httpx import ASGITransport, AsyncClient  # noqa: E402

from app.database import SessionLocal, init_db  # noqa: E402
from app.main import app  # noqa: E402
from app.seed import seed_all  # noqa: E402


@pytest_asyncio.fixture(scope="session", autouse=True)
async def prepare_db():
    await init_db()
    async with SessionLocal() as db:
        await seed_all(db)


@pytest_asyncio.fixture
async def client():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as c:
        yield c


@pytest_asyncio.fixture
async def auth_client(client: AsyncClient) -> AsyncClient:
    resp = await client.post(
        "/api/auth/login",
        json={"username": "admin", "password": "admin123"},
    )
    assert resp.status_code == 200
    return client


@pytest_asyncio.fixture
async def demo_ds_id(auth_client: AsyncClient) -> int:
    resp = await auth_client.get("/api/connections?page_size=50")
    data = resp.json()["data"]
    for item in data["list"]:
        if item["db_type"] == "sqlite":
            return item["id"]
    return 0
