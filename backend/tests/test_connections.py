"""连接管理测试。"""
import pytest


async def test_list_connections(auth_client):
    resp = await auth_client.get("/api/connections")
    assert resp.status_code == 200
    data = resp.json()["data"]
    assert data["total"] >= 1
    conn = data["list"][0]
    assert "has_password" in conn
    assert "password" not in conn


async def test_test_connection_sqlite(auth_client):
    resp = await auth_client.post(
        "/api/connections/test",
        json={"db_type": "sqlite", "database_name": ""},
    )
    assert resp.status_code == 200
    assert resp.json()["data"]["success"] is True


async def test_create_update_clone_delete(auth_client):
    payload = {
        "name": "测试连接",
        "db_type": "sqlite",
        "database_name": "",
        "environment": "test",
        "password": "pw123",
    }
    resp = await auth_client.post("/api/connections", json=payload)
    assert resp.status_code == 200
    conn = resp.json()["data"]
    cid = conn["id"]
    assert conn["has_password"] is True

    # 详情
    detail = await auth_client.get(f"/api/connections/{cid}")
    assert detail.status_code == 200
    assert detail.json()["data"]["name"] == "测试连接"

    # 更新
    upd = await auth_client.put(f"/api/connections/{cid}", json={**payload, "name": "测试连接2", "password": "newpw"})
    assert upd.status_code == 200
    assert upd.json()["data"]["name"] == "测试连接2"

    # 克隆
    clone = await auth_client.post(f"/api/connections/{cid}/clone")
    assert clone.status_code == 200
    clone_id = clone.json()["data"]["id"]
    assert clone_id != cid

    # 删除
    d1 = await auth_client.delete(f"/api/connections/{cid}")
    d2 = await auth_client.delete(f"/api/connections/{clone_id}")
    assert d1.status_code == 200 and d2.status_code == 200
    gone = await auth_client.get(f"/api/connections/{cid}")
    assert gone.status_code == 404


async def test_duplicate_name(auth_client):
    payload = {"name": "重名连接", "db_type": "sqlite", "database_name": ""}
    resp1 = await auth_client.post("/api/connections", json=payload)
    resp2 = await auth_client.post("/api/connections", json=payload)
    assert resp1.status_code == 200
    assert resp2.status_code == 400
    cid = resp1.json()["data"]["id"]
    await auth_client.delete(f"/api/connections/{cid}")
