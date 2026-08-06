"""元数据与收藏测试。"""
import pytest


async def test_schemas_tables(auth_client, demo_ds_id):
    schemas = await auth_client.get(f"/api/metadata/{demo_ds_id}/schemas")
    assert schemas.status_code == 200
    assert "main" in schemas.json()["data"]

    tables = await auth_client.get(f"/api/metadata/{demo_ds_id}/tables")
    names = tables.json()["data"]
    assert "users" in names and "orders" in names


async def test_table_columns(auth_client, demo_ds_id):
    resp = await auth_client.get(f"/api/metadata/{demo_ds_id}/tables/users/columns")
    assert resp.status_code == 200
    cols = resp.json()["data"]
    names = [c["name"] for c in cols]
    assert "id" in names and "username" in names
    pk = [c for c in cols if c["name"] == "id"][0]
    assert pk["primary_key"] is True


async def test_indexes_ddl_data(auth_client, demo_ds_id):
    idx = await auth_client.get(f"/api/metadata/{demo_ds_id}/tables/orders/indexes")
    assert idx.status_code == 200
    assert len(idx.json()["data"]) >= 1

    ddl = await auth_client.get(f"/api/metadata/{demo_ds_id}/tables/users/ddl")
    assert ddl.status_code == 200
    assert "CREATE TABLE" in ddl.json()["data"]["ddl"].upper()

    data = await auth_client.get(f"/api/metadata/{demo_ds_id}/tables/orders/data?page=1&size=5")
    assert data.status_code == 200
    body = data.json()["data"]
    assert body["total"] >= 10
    assert len(body["rows"]) <= 5


async def test_views_and_triggers(auth_client, demo_ds_id):
    views = await auth_client.get(f"/api/metadata/{demo_ds_id}/views")
    assert "v_user_orders" in views.json()["data"]
    vddl = await auth_client.get(f"/api/metadata/{demo_ds_id}/views/v_user_orders/ddl")
    assert vddl.status_code == 200
    assert "CREATE VIEW" in vddl.json()["data"]["ddl"].upper()

    triggers = await auth_client.get(f"/api/metadata/{demo_ds_id}/triggers")
    assert len(triggers.json()["data"]) >= 1


async def test_sequences_empty_sqlite(auth_client, demo_ds_id):
    resp = await auth_client.get(f"/api/metadata/{demo_ds_id}/sequences")
    assert resp.status_code == 200
    assert resp.json()["data"] == []


async def test_favorites(auth_client, demo_ds_id):
    add = await auth_client.post(
        f"/api/metadata/{demo_ds_id}/favorites",
        json={"schema_name": "main", "table_name": "products"},
    )
    assert add.status_code == 200
    listing = await auth_client.get(f"/api/metadata/{demo_ds_id}/favorites")
    names = [f["table_name"] for f in listing.json()["data"]]
    assert "products" in names
    rem = await auth_client.delete(f"/api/metadata/{demo_ds_id}/favorites/products")
    assert rem.status_code == 200
    listing2 = await auth_client.get(f"/api/metadata/{demo_ds_id}/favorites")
    assert "products" not in [f["table_name"] for f in listing2.json()["data"]]


async def test_alter_requires_ddl(auth_client, demo_ds_id):
    resp = await auth_client.post(
        f"/api/metadata/{demo_ds_id}/tables/users/alter",
        json={"ddl": "ALTER TABLE users ADD COLUMN phone TEXT"},
    )
    assert resp.status_code == 200
    data = resp.json()["data"]
    assert data["need_confirm"] is True
    assert data["risk_level"] == "danger"
