"""报表测试。"""
import pytest


async def test_chart_crud(auth_client, demo_ds_id):
    resp = await auth_client.post(
        "/api/charts",
        json={
            "name": "订单状态分布",
            "datasource_id": demo_ds_id,
            "sql_text": "SELECT status, COUNT(*) AS cnt FROM orders GROUP BY status",
            "chart_type": "pie",
            "x_column": "status",
            "y_column": "cnt",
        },
    )
    assert resp.status_code == 200
    chart = resp.json()["data"]
    chart_id = chart["id"]

    listing = await auth_client.get("/api/charts")
    assert any(c["id"] == chart_id for c in listing.json()["data"])

    data = await auth_client.get(f"/api/charts/{chart_id}/data")
    assert data.status_code == 200
    assert data.json()["data"]["rows"]

    upd = await auth_client.put(f"/api/charts/{chart_id}", json={"name": "订单分布 v2"})
    assert upd.json()["data"]["name"] == "订单分布 v2"

    dele = await auth_client.delete(f"/api/charts/{chart_id}")
    assert dele.status_code == 200


async def test_dashboard_crud_and_share(auth_client, demo_ds_id):
    chart = await auth_client.post(
        "/api/charts",
        json={
            "name": "销售汇总",
            "datasource_id": demo_ds_id,
            "sql_text": "SELECT status, SUM(amount) AS total FROM orders GROUP BY status",
            "chart_type": "bar",
            "x_column": "status",
            "y_column": "total",
        },
    )
    chart_id = chart.json()["data"]["id"]
    dash = await auth_client.post(
        "/api/dashboards",
        json={"name": "总览面板", "chart_ids": [chart_id]},
    )
    assert dash.status_code == 200
    dash_id = dash.json()["data"]["id"]

    share = await auth_client.post(f"/api/dashboards/{dash_id}/share")
    assert share.status_code == 200
    token = share.json()["data"]["share_token"]
    assert token

    pub = await auth_client.get(f"/api/share/{token}")
    assert pub.status_code == 200
    pub_data = pub.json()["data"]
    assert pub_data["dashboard"]["chart_ids"] == [chart_id]
    assert len(pub_data["charts"]) == 1
    assert pub_data["charts"][0]["id"] == chart_id
    assert pub_data["charts"][0]["rows"]

    pub_chart = await auth_client.get(f"/api/share/{token}/charts/{chart_id}/data")
    assert pub_chart.status_code == 200
    assert pub_chart.json()["data"]["rows"]

    detail = await auth_client.get(f"/api/dashboards/{dash_id}")
    assert detail.status_code == 200
    assert detail.json()["data"]["chart_ids"] == [chart_id]

    dele = await auth_client.delete(f"/api/dashboards/{dash_id}")
    await auth_client.delete(f"/api/charts/{chart_id}")
    assert dele.status_code == 200
