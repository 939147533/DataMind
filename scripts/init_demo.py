"""初始化/重建演示数据：应用库表、管理员账户、演示 SQLite 库、演示连接、默认 AI 配置。

用法:
    python scripts/init_demo.py
"""
import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "backend"))

from app.database import SessionLocal, init_db  # noqa: E402
from app.seed import seed_all  # noqa: E402


async def main() -> None:
    await init_db()
    async with SessionLocal() as db:
        await seed_all(db)
    print("初始化完成：admin/admin123、演示库 demo.db、演示连接、默认 AI 配置已就绪")


if __name__ == "__main__":
    asyncio.run(main())
