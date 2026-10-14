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


class _Row:
    """构造 _build_candidates 可消费的最小历史行。"""

    def __init__(self, sql_text: str):
        self.sql_text = sql_text


def test_rank_examples_prefers_table_match():
    from app.services.sql_examples import _build_candidates, rank_examples

    examples = _build_candidates(
        [
            _Row("SELECT * FROM zzbeta_items"),
            _Row("SELECT * FROM zzalpha_items"),
        ]
    )
    ranked = rank_examples(examples, "查询 zzalpha_items 的明细", limit=1)
    assert "zzalpha_items" in ranked[0].sql


def test_rank_examples_prefers_token_similarity():
    from app.services.sql_examples import _build_candidates, rank_examples

    examples = _build_candidates(
        [
            _Row("SELECT * FROM zzepsilon_items"),
            _Row("SELECT refund_amount FROM zzepsilon_items"),
        ]
    )
    ranked = rank_examples(examples, "refund_amount 是多少", limit=1)
    assert "refund_amount" in ranked[0].sql


def test_rank_examples_falls_back_to_frequency():
    from app.services.sql_examples import _build_candidates, rank_examples

    examples = _build_candidates(
        [
            _Row("SELECT * FROM zzdelta_items"),
            _Row("SELECT * FROM zzgamma_items"),
            _Row("SELECT * FROM zzgamma_items"),
            _Row("SELECT * FROM zzgamma_items"),
        ]
    )
    ranked = rank_examples(examples, "打个招呼", limit=1)
    assert "zzgamma_items" in ranked[0].sql


async def test_load_few_shots_accepts_question(auth_client, demo_ds_id):
    from app.database import SessionLocal
    from app.services.agent_service import _load_few_shots

    await auth_client.post(
        "/api/sql/execute",
        json={"datasource_id": demo_ds_id, "sql": "SELECT username FROM users LIMIT 2"},
    )
    async with SessionLocal() as db:
        text = await _load_few_shots(db, demo_ds_id, question="查询 users 表的用户名", limit=3)
    assert "SELECT" in text


async def test_few_shot_candidates_are_cached(auth_client, demo_ds_id):
    from app.database import SessionLocal
    from app.services import sql_examples

    await auth_client.post(
        "/api/sql/execute",
        json={"datasource_id": demo_ds_id, "sql": "SELECT username FROM users LIMIT 1"},
    )
    sql_examples.invalidate()
    async with SessionLocal() as db:
        first = await sql_examples.get_candidates(db, demo_ds_id)
    assert first
    assert demo_ds_id in sql_examples._cache
    async with SessionLocal() as db:
        second = await sql_examples.get_candidates(db, demo_ds_id)
    assert second is first  # 命中缓存：未重新查库、未重新解析


async def test_history_write_merges_into_cache(auth_client, demo_ds_id):
    from app.database import SessionLocal
    from app.services import sql_examples

    async with SessionLocal() as db:
        await sql_examples.get_candidates(db, demo_ds_id)
    assert demo_ds_id in sql_examples._cache
    sql = "SELECT username FROM users LIMIT 9"
    resp = await auth_client.post(
        "/api/sql/execute",
        json={"datasource_id": demo_ds_id, "sql": sql},
    )
    assert resp.status_code == 200
    _, updated = sql_examples._cache[demo_ds_id]
    assert any(example.sql == sql for example in updated)  # 增量并入而不是清空重建
