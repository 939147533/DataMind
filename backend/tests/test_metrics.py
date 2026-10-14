"""Prometheus 指标：访问控制与路径标签基数。"""


async def test_metrics_accessible_from_loopback(client):
    resp = await client.get("/metrics")
    assert resp.status_code == 200
    assert "http_requests_total" in resp.text


async def test_metrics_path_label_is_route_template(auth_client, demo_ds_id):
    """路径标签必须收敛到路由模板，否则每个 id 都会新增一条时间序列。"""
    await auth_client.get(f"/api/connections/{demo_ds_id}")
    resp = await auth_client.get("/metrics")
    text = resp.text
    assert 'path="/api/connections/{connection_id}"' in text
    assert f'path="/api/connections/{demo_ds_id}"' not in text


async def test_metrics_requires_token_when_configured(client, monkeypatch):
    monkeypatch.setattr("app.main.METRICS_TOKEN", "s3cret")
    assert (await client.get("/metrics")).status_code == 401
    assert (await client.get("/metrics?token=wrong")).status_code == 401
    assert (await client.get("/metrics?token=s3cret")).status_code == 200
    assert (await client.get("/metrics", headers={"Authorization": "Bearer s3cret"})).status_code == 200
    assert (await client.get("/metrics", headers={"Authorization": "Bearer nope"})).status_code == 401
