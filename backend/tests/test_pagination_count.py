"""分页总数与索引补建：总数用 count() 统计，老库自动补索引。"""


async def test_history_total_tracks_created_rows(auth_client, demo_ds_id):
    await auth_client.post(
        "/api/sql/execute",
        json={"datasource_id": demo_ds_id, "sql": "SELECT 1 AS one"},
    )
    resp = await auth_client.get(f"/api/sql/history?page=1&page_size=1&datasource_id={demo_ds_id}")
    assert resp.status_code == 200
    data = resp.json()["data"]
    assert data["total"] >= 1
    assert len(data["list"]) == 1

    from sqlalchemy import func, select

    from app.database import SessionLocal
    from app.models import QueryHistory

    async with SessionLocal() as db:
        expected = (
            await db.execute(
                select(func.count()).select_from(QueryHistory).where(QueryHistory.datasource_id == demo_ds_id)
            )
        ).scalar_one()
    assert data["total"] == expected


async def test_audit_total_matches_table_count(auth_client):
    from sqlalchemy import func, select

    from app.database import SessionLocal
    from app.models import AuditLog

    resp = await auth_client.get("/api/audit/logs?page=1&page_size=5")
    assert resp.status_code == 200
    data = resp.json()["data"]
    async with SessionLocal() as db:
        expected = (await db.execute(select(func.count()).select_from(AuditLog))).scalar_one()
    assert data["total"] == expected
    assert len(data["list"]) <= 5


async def test_users_total_matches_table_count(auth_client):
    from sqlalchemy import func, select

    from app.database import SessionLocal
    from app.models import User

    resp = await auth_client.get("/api/users?page=1&page_size=1")
    assert resp.status_code == 200
    data = resp.json()["data"]
    async with SessionLocal() as db:
        expected = (await db.execute(select(func.count()).select_from(User))).scalar_one()
    assert data["total"] == expected
    assert len(data["list"]) == 1


def test_missing_indexes_are_recreated(tmp_path):
    """模拟老库（表已存在但缺索引）：init_db 的补建逻辑应把索引加回来。"""
    from sqlalchemy import create_engine, inspect, text

    from app.database import Base, _create_missing_indexes
    from app import models  # noqa: F401  确保模型注册到 metadata

    engine = create_engine(f"sqlite:///{tmp_path / 'legacy.db'}")
    with engine.begin() as conn:
        Base.metadata.create_all(conn)
        conn.execute(text("DROP INDEX ix_audit_logs_created_at"))
        conn.execute(text("DROP INDEX ix_agent_messages_session_id"))
        existing = {ix["name"] for ix in inspect(conn).get_indexes("audit_logs")}
        assert "ix_audit_logs_created_at" not in existing

        _create_missing_indexes(conn)

        after_audit = {ix["name"] for ix in inspect(conn).get_indexes("audit_logs")}
        after_msg = {ix["name"] for ix in inspect(conn).get_indexes("agent_messages")}
    assert "ix_audit_logs_created_at" in after_audit
    assert "ix_agent_messages_session_id" in after_msg
    engine.dispose()


async def test_audit_total_uses_sql_count(auth_client):
    """总数必须走 COUNT 查询，而不是把全量行拉进内存再 len()。"""
    from app.database import SessionLocal, get_db
    from app.main import app

    seen: list[str] = []

    async def spy_db():
        async with SessionLocal() as session:
            original = session.execute

            async def execute(stmt, *args, **kwargs):
                try:
                    seen.append(str(stmt))
                except Exception:  # noqa: BLE001
                    seen.append("")
                return await original(stmt, *args, **kwargs)

            session.execute = execute
            yield session

    app.dependency_overrides[get_db] = spy_db
    try:
        resp = await auth_client.get("/api/audit/logs?page=1&page_size=2")
        assert resp.status_code == 200
    finally:
        app.dependency_overrides.pop(get_db, None)

    assert any("count(" in sql.lower() for sql in seen), f"未使用 COUNT 统计总数: {seen}"


def test_models_declare_expected_indexes():
    from app.database import Base
    from app import models  # noqa: F401

    indexed = {
        (t.name, ix.name)
        for t in Base.metadata.sorted_tables
        for ix in t.indexes
    }
    for table, column in [
        ("query_history", "datasource_id"),
        ("audit_logs", "created_at"),
        ("agent_messages", "session_id"),
        ("dashboards", "share_token"),
        ("scheduled_exports", "next_run_at"),
    ]:
        assert (table, f"ix_{table}_{column}") in indexed, f"{table}.{column} 应建索引"
