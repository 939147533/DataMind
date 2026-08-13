"""SQL 收藏/模板测试。"""


async def test_saved_query_crud(auth_client, demo_ds_id):
    resp = await auth_client.post(
        "/api/saved-queries",
        json={"name": "查用户", "sql_text": "SELECT * FROM users", "datasource_id": demo_ds_id},
    )
    assert resp.status_code == 200
    qid = resp.json()["data"]["id"]

    lst = await auth_client.get("/api/saved-queries")
    assert any(q["id"] == qid for q in lst.json()["data"]["list"])

    upd = await auth_client.put(f"/api/saved-queries/{qid}", json={"name": "查用户 v2"})
    assert upd.json()["data"]["name"] == "查用户 v2"

    dele = await auth_client.delete(f"/api/saved-queries/{qid}")
    assert dele.status_code == 200
