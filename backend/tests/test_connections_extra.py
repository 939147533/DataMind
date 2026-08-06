"""连接管理补充测试。"""
import pytest


async def test_search_and_environment_filter(auth_client, demo_ds_id):
    payload = {"name": "搜索专用连接", "db_type": "sqlite", "database_name": "", "environment": "prod"}
    resp = await auth_client.post("/api/connections", json=payload)
    cid = resp.json()["data"]["id"]

    found = await auth_client.get("/api/connections?search=搜索专用")
    assert any(c["name"] == "搜索专用连接" for c in found.json()["data"]["list"])

    env = await auth_client.get("/api/connections?environment=prod")
    assert any(c["id"] == cid for c in env.json()["data"]["list"])

    await auth_client.delete(f"/api/connections/{cid}")


async def test_connect_demo(auth_client, demo_ds_id):
    resp = await auth_client.post(f"/api/connections/{demo_ds_id}/connect")
    assert resp.status_code == 200
    assert "main" in resp.json()["data"]["schemas"]


async def test_test_connection_bad_file(auth_client):
    resp = await auth_client.post(
        "/api/connections/test",
        json={"db_type": "sqlite", "database_name": "no_such_file_xyz.db"},
    )
    assert resp.status_code == 200
    assert resp.json()["data"]["success"] is False


async def test_unsupported_db_type(auth_client):
    resp = await auth_client.post(
        "/api/connections/test",
        json={"db_type": "nosql_unknown", "host": "localhost"},
    )
    assert resp.status_code == 400
