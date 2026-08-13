"""定时导出测试。"""


async def test_schedule_crud_and_run(auth_client, demo_ds_id):
    resp = await auth_client.post(
        "/api/schedule",
        json={
            "name": "每日订单导出",
            "datasource_id": demo_ds_id,
            "sql_text": "SELECT id, status FROM orders LIMIT 5",
            "format": "csv",
            "interval_minutes": 60,
            "enabled": True,
        },
    )
    assert resp.status_code == 200
    sid = resp.json()["data"]["id"]

    lst = await auth_client.get("/api/schedule")
    assert any(s["id"] == sid for s in lst.json()["data"])

    run = await auth_client.post(f"/api/schedule/{sid}/run")
    assert run.status_code == 200
    assert run.json()["data"]["file"]

    dl = await auth_client.get(f"/api/schedule/{sid}/file")
    assert dl.status_code == 200
    assert b"id" in dl.content and b"status" in dl.content

    upd = await auth_client.put(f"/api/schedule/{sid}", json={"enabled": False})
    assert upd.json()["data"]["enabled"] is False

    dele = await auth_client.delete(f"/api/schedule/{sid}")
    assert dele.status_code == 200
