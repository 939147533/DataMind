"""表数据行编辑测试（经 SQL 安全确认协议）。"""


async def _confirm(auth_client, execution_id):
    resp = await auth_client.post(
        "/api/sql/execute/confirm",
        json={"execution_id": execution_id, "confirmed": True},
    )
    assert resp.status_code == 200
    return resp.json()["data"]


async def _categories(auth_client, demo_ds_id):
    resp = await auth_client.get(f"/api/metadata/{demo_ds_id}/tables/categories/data?page=1&size=100")
    assert resp.status_code == 200
    return resp.json()["data"]["rows"]


async def test_table_row_insert_update_delete(auth_client, demo_ds_id):
    # 插入
    resp = await auth_client.post(
        f"/api/metadata/{demo_ds_id}/tables/categories/rows",
        json={"values": {"name": "待改分类", "description": "temp"}},
    )
    assert resp.status_code == 200
    data = resp.json()["data"]
    assert data["need_confirm"] is True
    result = await _confirm(auth_client, data["execution_id"])
    assert result["status"] == "executed"

    rows = await _categories(auth_client, demo_ds_id)
    target = [r for r in rows if r[1] == "待改分类"]
    assert target
    new_id = target[0][0]

    # 更新
    resp = await auth_client.post(
        f"/api/metadata/{demo_ds_id}/tables/categories/data",
        json={"set_values": {"name": "已改分类"}, "where": {"id": new_id}},
    )
    data = resp.json()["data"]
    result = await _confirm(auth_client, data["execution_id"])
    assert result["status"] == "executed"
    rows = await _categories(auth_client, demo_ds_id)
    assert any(r[0] == new_id and r[1] == "已改分类" for r in rows)

    # 删除
    resp = await auth_client.post(
        f"/api/metadata/{demo_ds_id}/tables/categories/rows/delete",
        json={"where": {"id": new_id}},
    )
    data = resp.json()["data"]
    result = await _confirm(auth_client, data["execution_id"])
    assert result["status"] == "executed"
    rows = await _categories(auth_client, demo_ds_id)
    assert not any(r[0] == new_id for r in rows)


async def test_table_delete_requires_where(auth_client, demo_ds_id):
    resp = await auth_client.post(
        f"/api/metadata/{demo_ds_id}/tables/categories/rows/delete",
        json={"where": {}},
    )
    assert resp.status_code == 400
