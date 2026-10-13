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


import sqlite3  # noqa: E402

from app import config  # noqa: E402
from app.adapters.base import base_data_type, column_length  # noqa: E402
from app.services.metadata_service import diff_columns  # noqa: E402


def test_column_length_helper():
    assert column_length("VARCHAR(255)") == "255"
    assert column_length("varchar", char_length=120) == "120"
    assert column_length("decimal", numeric_precision=10, numeric_scale=2) == "10,2"
    assert column_length("NUMBER", numeric_precision=12) == "12"
    assert column_length("int", numeric_precision=11) == ""
    assert column_length("text") == ""


def test_base_data_type_helper():
    assert base_data_type("VARCHAR(255)") == "varchar"
    assert base_data_type("CHARACTER VARYING") == "character varying"


def test_diff_columns_detects_length_change():
    diffs = diff_columns(
        [{"name": "name", "data_type": "varchar", "length": "50"}],
        [{"name": "name", "data_type": "varchar", "length": "100"}],
    )
    assert len(diffs) == 1
    assert diffs[0] == {"column": "name", "source_type": "varchar", "target_type": "varchar", "source_length": "50", "target_length": "100"}


def test_diff_columns_treats_sqlite_inline_length_as_equal():
    src = [{"name": "name", "data_type": "VARCHAR(50)"}]
    tgt = [{"name": "name", "data_type": "varchar", "length": "50"}]
    assert diff_columns(src, tgt) == []


async def test_monitor_schema_diff_detects_length(auth_client):
    created = []
    try:
        for filename, length in (("diff_a.db", 50), ("diff_b.db", 100)):
            conn = sqlite3.connect(str(config.DATA_DIR / filename))
            conn.execute(f"CREATE TABLE IF NOT EXISTS items (id INTEGER PRIMARY KEY, name VARCHAR({length}))")
            conn.commit()
            conn.close()
            resp = await auth_client.post(
                "/api/connections",
                json={"name": f"diff-{length}", "db_type": "sqlite", "database_name": filename},
            )
            assert resp.status_code == 200
            created.append(resp.json()["data"]["id"])
        resp = await auth_client.post(
            "/api/monitor/schema-diff",
            json={"source_ds_id": created[0], "target_ds_id": created[1]},
        )
        assert resp.status_code == 200
        data = resp.json()["data"]
        assert data["only_source"] == []
        assert data["only_target"] == []
        assert len(data["table_diffs"]) == 1
        changed = data["table_diffs"][0]["changed_columns"]
        assert changed[0]["column"] == "name"
        assert changed[0]["source_length"] == "50"
        assert changed[0]["target_length"] == "100"
    finally:
        for cid in created:
            await auth_client.delete(f"/api/connections/{cid}")
