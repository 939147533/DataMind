"""SQL 执行授权协议测试。"""
import pytest


async def test_read_auto_execute(auth_client, demo_ds_id):
    resp = await auth_client.post(
        "/api/sql/execute",
        json={"datasource_id": demo_ds_id, "sql": "SELECT status, COUNT(*) AS cnt FROM orders GROUP BY status"},
    )
    assert resp.status_code == 200
    data = resp.json()["data"]
    assert data["need_confirm"] is False
    assert "status" in data["columns"]
    assert data["total_rows"] >= 1


async def test_multi_statements(auth_client, demo_ds_id):
    resp = await auth_client.post(
        "/api/sql/execute",
        json={"datasource_id": demo_ds_id, "sql": "SELECT COUNT(*) AS c FROM users; SELECT AVG(amount) AS avg FROM orders"},
    )
    assert resp.status_code == 200
    data = resp.json()["data"]
    assert data["columns"] == ["avg"]


async def test_dml_requires_confirm(auth_client, demo_ds_id):
    resp = await auth_client.post(
        "/api/sql/execute",
        json={"datasource_id": demo_ds_id, "sql": "UPDATE orders SET status='paid' WHERE id=1"},
    )
    assert resp.status_code == 200
    data = resp.json()["data"]
    assert data["need_confirm"] is True
    assert data["risk_level"] == "warning"
    assert data["execution_id"]


async def test_confirm_executes(auth_client, demo_ds_id):
    resp = await auth_client.post(
        "/api/sql/execute",
        json={"datasource_id": demo_ds_id, "sql": "UPDATE orders SET status='paid' WHERE id=2"},
    )
    execution_id = resp.json()["data"]["execution_id"]
    confirm = await auth_client.post(
        "/api/sql/execute/confirm",
        json={"execution_id": execution_id, "confirmed": True},
    )
    assert confirm.status_code == 200
    data = confirm.json()["data"]
    assert data["status"] == "executed"


async def test_reject_does_not_execute(auth_client, demo_ds_id):
    resp = await auth_client.post(
        "/api/sql/execute",
        json={"datasource_id": demo_ds_id, "sql": "CREATE TABLE should_not_exist_tmp(id INTEGER)"},
    )
    data = resp.json()["data"]
    assert data["risk_level"] == "danger"
    cancel = await auth_client.post(
        "/api/sql/execute/confirm",
        json={"execution_id": data["execution_id"], "confirmed": False},
    )
    assert cancel.status_code == 200
    assert cancel.json()["data"]["status"] == "cancelled"
    check = await auth_client.post(
        "/api/sql/execute",
        json={"datasource_id": demo_ds_id, "sql": "SELECT name FROM sqlite_master WHERE name='should_not_exist_tmp'"},
    )
    assert check.json()["data"]["total_rows"] == 0


async def test_confirm_invalid_id(auth_client):
    resp = await auth_client.post(
        "/api/sql/execute/confirm",
        json={"execution_id": "no-such-id", "confirmed": True},
    )
    assert resp.status_code == 400


async def test_bad_sql_returns_400(auth_client, demo_ds_id):
    resp = await auth_client.post(
        "/api/sql/execute",
        json={"datasource_id": demo_ds_id, "sql": "SELECT * FROM no_such_table"},
    )
    assert resp.status_code == 400


async def test_datasource_not_found(auth_client):
    resp = await auth_client.post(
        "/api/sql/execute",
        json={"datasource_id": 999999, "sql": "SELECT 1"},
    )
    assert resp.status_code == 404


async def test_format_sql(auth_client):
    resp = await auth_client.post("/api/sql/format", json={"sql": "select * from users"})
    assert resp.status_code == 200
    assert "SELECT" in resp.json()["data"]["sql"].upper()


async def test_history(auth_client, demo_ds_id):
    resp = await auth_client.get(f"/api/sql/history?datasource_id={demo_ds_id}")
    assert resp.status_code == 200
    assert resp.json()["data"]["total"] >= 1
