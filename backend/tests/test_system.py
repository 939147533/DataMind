"""系统管理测试。"""
import io
import pytest


async def test_ai_config_crud(auth_client):
    resp = await auth_client.post(
        "/api/config/ai",
        json={
            "provider": "openai",
            "api_key": "sk-test-123",
            "api_base": "https://api.openai.com/v1",
            "model_name": "gpt-4o-mini",
            "is_active": True,
        },
    )
    assert resp.status_code == 200
    data = resp.json()["data"]
    cfg_id = data["id"]
    assert data["has_key"] is True

    listing = await auth_client.get("/api/config/ai")
    assert any(c["id"] == cfg_id for c in listing.json()["data"])

    upd = await auth_client.put(f"/api/config/ai/{cfg_id}", json={"model_name": "gpt-4o"})
    assert upd.json()["data"]["model_name"] == "gpt-4o"

    dflt = await auth_client.put(f"/api/config/ai/{cfg_id}/default")
    assert dflt.status_code == 200

    dele = await auth_client.delete(f"/api/config/ai/{cfg_id}")
    assert dele.status_code == 200


async def test_settings_get_put(auth_client):
    resp = await auth_client.get("/api/config/settings")
    assert resp.status_code == 200
    assert resp.json()["data"]["values"]["theme"] == "light"

    upd = await auth_client.put("/api/config/settings", json={"values": {"theme": "dark", "editor_font_size": "16"}})
    assert upd.status_code == 200
    resp2 = await auth_client.get("/api/config/settings")
    assert resp2.json()["data"]["values"]["theme"] == "dark"
    assert resp2.json()["data"]["values"]["editor_font_size"] == "16"


async def test_driver_upload_list_delete(auth_client):
    files = {"file": ("ojdbc.jar", io.BytesIO(b"fake-jar-content"), "application/java-archive")}
    resp = await auth_client.post(
        "/api/config/drivers",
        files=files,
        data={"db_type": "oracle", "driver_class": "oracle.jdbc.OracleDriver", "version": "23.4"},
    )
    assert resp.status_code == 200
    driver_id = resp.json()["data"]["id"]

    listing = await auth_client.get("/api/config/drivers")
    assert any(d["id"] == driver_id for d in listing.json()["data"])

    dele = await auth_client.delete(f"/api/config/drivers/{driver_id}")
    assert dele.status_code == 200


async def test_audit_logs(auth_client, demo_ds_id):
    resp = await auth_client.get("/api/audit/logs?page_size=10")
    assert resp.status_code == 200
    assert resp.json()["data"]["total"] >= 1
