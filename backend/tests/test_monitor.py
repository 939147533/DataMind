"""运维监控测试。"""


async def _run_query(auth_client, demo_ds_id, sql):
    resp = await auth_client.post("/api/sql/execute", json={"datasource_id": demo_ds_id, "sql": sql})
    assert resp.status_code == 200
    return resp.json()["data"]


async def test_monitor_overview(auth_client, demo_ds_id):
    await _run_query(auth_client, demo_ds_id, "SELECT username FROM users LIMIT 5")
    ov = await auth_client.get("/api/monitor/overview")
    assert ov.status_code == 200
    data = ov.json()["data"]
    assert data["total_queries"] >= 1
    assert any(d["datasource_id"] == demo_ds_id for d in data["datasources"])


async def test_monitor_slow_queries(auth_client, demo_ds_id):
    await _run_query(auth_client, demo_ds_id, "SELECT * FROM orders")
    sq = await auth_client.get("/api/monitor/slow-queries?threshold_ms=1")
    assert sq.status_code == 200
    assert "total" in sq.json()["data"]


async def test_monitor_schema_diff_same_source(auth_client, demo_ds_id):
    resp = await auth_client.post(
        "/api/monitor/schema-diff",
        json={"source_ds_id": demo_ds_id, "target_ds_id": demo_ds_id},
    )
    assert resp.status_code == 200
    data = resp.json()["data"]
    assert data["only_source"] == []
    assert data["only_target"] == []
    assert data["table_diffs"] == []
