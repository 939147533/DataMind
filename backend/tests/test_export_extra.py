"""导出补充测试。"""
import time

import pytest


async def test_export_result_json(auth_client, demo_ds_id):
    resp = await auth_client.post(
        "/api/export/result?format=json",
        json={"datasource_id": demo_ds_id, "sql": "SELECT username FROM users LIMIT 2"},
    )
    assert resp.status_code == 200
    import json as _json

    data = _json.loads(resp.content.decode("utf-8"))
    assert data[0]["username"]


async def test_export_database_word(auth_client, demo_ds_id):
    resp = await auth_client.post(
        "/api/export/database?format=word",
        json={"datasource_id": demo_ds_id, "tables": ["users"]},
    )
    assert resp.status_code == 200
    task_id = resp.json()["data"]["task_id"]
    for _ in range(20):
        time.sleep(0.2)
        st = await auth_client.get(f"/api/export/database/status/{task_id}")
        if st.json()["data"]["status"] in ("done", "failed"):
            break
    assert st.json()["data"]["status"] == "done"
    dl = await auth_client.get(st.json()["data"]["download_url"])
    assert dl.content[:2] == b"PK"


async def test_export_database_excel(auth_client, demo_ds_id):
    resp = await auth_client.post(
        "/api/export/database?format=excel",
        json={"datasource_id": demo_ds_id, "tables": ["users", "orders"]},
    )
    task_id = resp.json()["data"]["task_id"]
    for _ in range(20):
        time.sleep(0.2)
        st = await auth_client.get(f"/api/export/database/status/{task_id}")
        if st.json()["data"]["status"] in ("done", "failed"):
            break
    assert st.json()["data"]["status"] == "done"
    dl = await auth_client.get(st.json()["data"]["download_url"])
    assert dl.content[:2] == b"PK"


async def test_export_task_404(auth_client):
    resp = await auth_client.get("/api/export/database/status/no-such-task")
    assert resp.status_code == 404
