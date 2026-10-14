"""导出补充测试。"""
import time



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


async def test_export_result_records_audit(auth_client, demo_ds_id):
    """导出取数会连目标库，属于敏感操作，必须留审计。"""
    sql = "SELECT username FROM users LIMIT 3"
    resp = await auth_client.post(
        "/api/export/result?format=csv",
        json={"datasource_id": demo_ds_id, "sql": sql},
    )
    assert resp.status_code == 200

    logs = await auth_client.get("/api/audit/logs?action_type=export_result&page_size=20")
    items = logs.json()["data"]["list"]
    assert any(it["sql_text"] == sql and it["status"] == "success" for it in items), items


async def test_export_result_write_sql_is_rejected_and_audited(auth_client, demo_ds_id):
    resp = await auth_client.post(
        "/api/export/result?format=csv",
        json={"datasource_id": demo_ds_id, "sql": "UPDATE users SET display_name='x' WHERE id=1"},
    )
    assert resp.status_code == 400

    logs = await auth_client.get("/api/audit/logs?action_type=export_result&page_size=20")
    items = logs.json()["data"]["list"]
    assert any(it["status"] == "failed" for it in items), items


async def test_export_database_records_audit(auth_client, demo_ds_id):
    resp = await auth_client.post(
        "/api/export/database?format=markdown",
        json={"datasource_id": demo_ds_id, "tables": ["users"]},
    )
    assert resp.status_code == 200
    logs = await auth_client.get("/api/audit/logs?action_type=export_database&page_size=20")
    items = logs.json()["data"]["list"]
    assert items, "库文档导出应写入审计"
    assert items[0]["datasource_id"] == demo_ds_id
