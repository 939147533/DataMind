"""AI Agent 工具与 few-shot 辅助函数测试（不调用真实 LLM）。"""


async def test_load_few_shots(auth_client, demo_ds_id):
    resp = await auth_client.post(
        "/api/sql/execute",
        json={"datasource_id": demo_ds_id, "sql": "SELECT username FROM users LIMIT 2"},
    )
    assert resp.status_code == 200
    from app.database import SessionLocal
    from app.services.agent_service import _load_few_shots

    async with SessionLocal() as db:
        text = await _load_few_shots(db, demo_ds_id, limit=3)
    assert "SELECT" in text


async def test_run_tool_list_tables(auth_client, demo_ds_id):
    from app.database import SessionLocal
    from app.services.agent_service import _run_tool
    from app.services.sql_service import get_datasource

    async with SessionLocal() as db:
        ds = await get_datasource(db, demo_ds_id)
        result = _run_tool(ds, "list_tables", {})
    assert "users" in result


async def test_run_tool_get_columns(auth_client, demo_ds_id):
    from app.database import SessionLocal
    from app.services.agent_service import _run_tool
    from app.services.sql_service import get_datasource

    async with SessionLocal() as db:
        ds = await get_datasource(db, demo_ds_id)
        result = _run_tool(ds, "get_columns", {"table": "users"})
    assert "username" in result


async def test_run_tool_sample_data(auth_client, demo_ds_id):
    from app.database import SessionLocal
    from app.services.agent_service import _run_tool
    from app.services.sql_service import get_datasource

    async with SessionLocal() as db:
        ds = await get_datasource(db, demo_ds_id)
        result = _run_tool(ds, "sample_data", {"table": "users", "limit": 3})
    assert "alice" in result
