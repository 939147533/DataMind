"""启动种子：默认账户、内置角色、演示 SQLite 库、演示连接、默认 AI 配置、系统设置。"""
import json
import sqlite3
from datetime import datetime, timedelta

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from .config import DEFAULT_PASSWORD, DEFAULT_USERNAME, DEMO_DB_PATH
from .models import AIConfig, DataSource, Role, Setting, User
from .permissions import BUILTIN_ROLES
from .security import encrypt_text, hash_password


def _ensure_demo_db() -> str:
    """创建（如不存在）演示 SQLite 数据库，返回相对数据目录的文件名。"""
    if DEMO_DB_PATH.exists():
        return DEMO_DB_PATH.name
    conn = sqlite3.connect(str(DEMO_DB_PATH))
    cur = conn.cursor()
    cur.executescript(
        """
        CREATE TABLE categories (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            description TEXT
        );
        CREATE TABLE products (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            category_id INTEGER REFERENCES categories(id),
            price REAL NOT NULL DEFAULT 0,
            stock INTEGER NOT NULL DEFAULT 0
        );
        CREATE TABLE users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT NOT NULL UNIQUE,
            email TEXT NOT NULL,
            age INTEGER,
            created_at TEXT NOT NULL
        );
        CREATE TABLE orders (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL REFERENCES users(id),
            product_id INTEGER NOT NULL REFERENCES products(id),
            quantity INTEGER NOT NULL DEFAULT 1,
            amount REAL NOT NULL DEFAULT 0,
            status TEXT NOT NULL DEFAULT 'pending',
            created_at TEXT NOT NULL
        );
        CREATE TABLE order_logs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            order_id INTEGER NOT NULL,
            action TEXT NOT NULL,
            created_at TEXT NOT NULL
        );
        CREATE INDEX idx_products_category ON products(category_id);
        CREATE INDEX idx_orders_user ON orders(user_id);
        CREATE VIEW v_user_orders AS
            SELECT u.username, p.name AS product, o.quantity, o.amount, o.status, o.created_at
            FROM orders o
            JOIN users u ON u.id = o.user_id
            JOIN products p ON p.id = o.product_id;
        CREATE TRIGGER log_new_order AFTER INSERT ON orders
        BEGIN
            INSERT INTO order_logs(order_id, action, created_at) VALUES (NEW.id, 'created', datetime('now'));
        END;
        """
    )
    now = datetime.now()
    categories = [
        ("电子产品", "数码与配件"),
        ("图书", "书籍与杂志"),
        ("食品", "零食与饮料"),
        ("服装", "服饰鞋帽"),
        ("家居", "家装日用品"),
    ]
    cur.executemany("INSERT INTO categories(name, description) VALUES (?, ?)", categories)
    products = [
        ("智能手机", 1, 2999.0, 120),
        ("笔记本电脑", 1, 5999.0, 45),
        ("无线耳机", 1, 399.0, 300),
        ("Python 编程入门", 2, 79.0, 500),
        ("数据库设计实战", 2, 99.0, 320),
        ("坚果礼盒", 3, 129.0, 200),
        ("气泡水", 3, 6.5, 1000),
        ("纯棉T恤", 4, 59.0, 800),
        ("运动鞋", 4, 299.0, 150),
        ("台灯", 5, 89.0, 260),
    ]
    cur.executemany("INSERT INTO products(name, category_id, price, stock) VALUES (?, ?, ?, ?)", products)
    users = [
        ("alice", "alice@example.com", 28, "2026-01-05 09:12:00"),
        ("bob", "bob@example.com", 34, "2026-01-12 14:30:00"),
        ("carol", "carol@example.com", 25, "2026-02-03 10:00:00"),
        ("dave", "dave@example.com", 41, "2026-02-15 16:45:00"),
        ("eve", "eve@example.com", 30, "2026-03-02 08:20:00"),
        ("frank", "frank@example.com", 22, "2026-03-18 11:05:00"),
        ("grace", "grace@example.com", 37, "2026-04-01 13:40:00"),
        ("heidi", "heidi@example.com", 29, "2026-04-20 09:55:00"),
    ]
    cur.executemany("INSERT INTO users(username, email, age, created_at) VALUES (?, ?, ?, ?)", users)
    import random

    random.seed(42)
    orders = []
    order_id = 1
    for day in range(1, 40):
        for _ in range(random.randint(1, 3)):
            user_id = random.randint(1, 8)
            product_id = random.randint(1, 10)
            qty = random.randint(1, 3)
            price = products[product_id - 1][2]
            amount = round(price * qty, 2)
            status = random.choice(["pending", "paid", "shipped", "done"])
            created = f"2026-07-{day:02d} {random.randint(8, 20):02d}:{random.randint(0, 59):02d}:00"
            orders.append((user_id, product_id, qty, amount, status, created))
            order_id += 1
    cur.executemany(
        "INSERT INTO orders(user_id, product_id, quantity, amount, status, created_at) VALUES (?, ?, ?, ?, ?, ?)",
        orders,
    )
    conn.commit()
    conn.close()
    return DEMO_DB_PATH.name


async def seed_all(db: AsyncSession) -> None:
    # 内置角色（固定 5 个：管理员/技术管理/技术查询/业务管理/业务查询）
    for r in BUILTIN_ROLES:
        role = (await db.execute(select(Role).where(Role.code == r["code"]))).scalar_one_or_none()
        if role is None:
            db.add(
                Role(
                    code=r["code"],
                    name=r["name"],
                    description=r["description"],
                    permissions=json.dumps(r["permissions"], ensure_ascii=False),
                    is_builtin=True,
                )
            )
        else:
            role.name = r["name"]
            role.description = r["description"]
            role.is_builtin = True
    await db.commit()

    # 默认管理员
    user = (await db.execute(select(User).where(User.username == DEFAULT_USERNAME))).scalar_one_or_none()
    if user is None:
        db.add(
            User(
                username=DEFAULT_USERNAME,
                password_hash=hash_password(DEFAULT_PASSWORD),
                display_name="管理员",
                role="admin",
            )
        )
        await db.commit()

    # 演示数据库文件
    demo_path = _ensure_demo_db()

    # 演示连接（database_name 存相对数据目录的文件名，项目目录改名/移动后依然可用）
    ds = (await db.execute(select(DataSource).where(DataSource.name == "本地演示库 (SQLite)"))).scalar_one_or_none()
    if ds is None:
        db.add(
            DataSource(
                name="本地演示库 (SQLite)",
                db_type="sqlite",
                database_name=demo_path,
                environment="dev",
                status="unknown",
                description="内置演示数据库：用户/商品/订单等表，含视图与触发器",
            )
        )
        await db.commit()
    elif (ds.database_name or "").strip() != demo_path:
        ds.database_name = demo_path
        await db.commit()

    # 默认 AI 配置（OpenAI 兼容，密钥留空由用户填写）
    cfg = (await db.execute(select(AIConfig))).scalars().first()
    if cfg is None:
        db.add(
            AIConfig(
                provider="openai",
                api_key=encrypt_text(""),
                api_base="https://api.openai.com/v1",
                model_name="gpt-4o-mini",
                max_tokens=4096,
                temperature=0.7,
                is_active=True,
                is_default=True,
            )
        )
        await db.commit()

    # 默认系统设置
    for key, value in {
        "language": "zh",
        "theme": "light",
        "editor_font_size": "14",
        "editor_tab_size": "4",
        "autocomplete": "true",
        "audit_retention_days": "180",
    }.items():
        setting = (await db.execute(select(Setting).where(Setting.key == key))).scalar_one_or_none()
        if setting is None:
            db.add(Setting(key=key, value=value))
    await db.commit()
