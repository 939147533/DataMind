"""导出测试。"""
import pytest


async def test_export_result_csv(auth_client, demo_ds_id):
    resp = await auth_client.post(
        f"/api/export/result?format=csv",
        json={"datasource_id": demo_ds_id, "sql": "SELECT username, age FROM users LIMIT 3"},
    )
    assert resp.status_code == 200
    body = resp.content
    assert b"username" in body and b"alice" in body


async def test_export_result_excel(auth_client, demo_ds_id):
    resp = await auth_client.post(
        f"/api/export/result?format=excel",
        json={"datasource_id": demo_ds_id, "sql": "SELECT username FROM users LIMIT 2"},
    )
    assert resp.status_code == 200
    assert resp.content[:2] == b"PK"  # xlsx 是 zip 格式


async def test_export_database_markdown(auth_client, demo_ds_id):
    resp = await auth_client.post(
        f"/api/export/database?format=markdown",
        json={"datasource_id": demo_ds_id, "tables": ["users", "orders"]},
    )
    assert resp.status_code == 200
    task_id = resp.json()["data"]["task_id"]
    import time

    status = None
    for _ in range(20):
        time.sleep(0.2)
        st = await auth_client.get(f"/api/export/database/status/{task_id}")
        status = st.json()["data"]["status"]
        if status in ("done", "failed"):
            break
    assert status == "done"
    assert "download_url" in st.json()["data"]
    dl = await auth_client.get(st.json()["data"]["download_url"])
    assert dl.status_code == 200
    assert b"users" in dl.content


async def test_export_rejects_write_sql(auth_client, demo_ds_id):
    resp = await auth_client.post(
        "/api/export/result?format=csv",
        json={"datasource_id": demo_ds_id, "sql": "DELETE FROM users"},
    )
    assert resp.status_code == 400
