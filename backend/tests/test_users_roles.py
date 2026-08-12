# -*- coding: utf-8 -*-
"""用户管理、角色管理、功能权限测试。"""
import pytest
from httpx import ASGITransport, AsyncClient

from app.main import app


async def _new_client() -> AsyncClient:
    transport = ASGITransport(app=app)
    return AsyncClient(transport=transport, base_url="http://test")


async def _login(client: AsyncClient, username: str, password: str):
    resp = await client.post("/api/auth/login", json={"username": username, "password": password})
    assert resp.status_code == 200, resp.text
    return resp.json()["data"]


async def _create_user(auth_client, username, role="tech_query", password="test1234"):
    resp = await auth_client.post(
        "/api/users",
        json={"username": username, "password": password, "display_name": username, "role": role, "is_active": True},
    )
    assert resp.status_code == 200, resp.text
    return resp.json()["data"]["id"]


# ---------- 角色种子 ----------
async def test_roles_seeded(auth_client):
    resp = await auth_client.get("/api/roles")
    assert resp.status_code == 200
    roles = resp.json()["data"]
    codes = {r["code"] for r in roles}
    assert {"admin", "tech_manager", "tech_query", "biz_manager", "biz_query"} <= codes
    admin = next(r for r in roles if r["code"] == "admin")
    assert admin["is_builtin"] is True
    assert "*" in admin["permissions"]


async def test_login_returns_permissions(auth_client):
    resp = await auth_client.get("/api/auth/me")
    data = resp.json()["data"]
    assert "*" in data["permissions"]


# ---------- 用户管理 ----------
async def test_create_and_list_users(auth_client):
    uid = await _create_user(auth_client, "user_tech", role="tech_query")
    assert uid > 0
    resp = await auth_client.get("/api/users?search=user_tech")
    assert resp.status_code == 200
    items = resp.json()["data"]["list"]
    assert any(u["username"] == "user_tech" for u in items)


async def test_create_duplicate_username(auth_client):
    await _create_user(auth_client, "dup_user")
    resp = await auth_client.post(
        "/api/users", json={"username": "dup_user", "password": "test1234", "role": "tech_query"}
    )
    assert resp.status_code == 400


async def test_create_invalid_role(auth_client):
    resp = await auth_client.post(
        "/api/users", json={"username": "bad_role", "password": "test1234", "role": "no_such_role"}
    )
    assert resp.status_code == 400


async def test_update_user(auth_client):
    uid = await _create_user(auth_client, "upd_user")
    resp = await auth_client.put(
        f"/api/users/{uid}",
        json={"display_name": "新名字", "role": "biz_manager", "password": "newpass123"},
    )
    assert resp.status_code == 200
    data = resp.json()["data"]
    assert data["role"] == "biz_manager"
    assert data["display_name"] == "新名字"


async def test_cannot_disable_self(auth_client):
    me = (await auth_client.get("/api/auth/me")).json()["data"]
    resp = await auth_client.put(f"/api/users/{me['id']}", json={"is_active": False})
    assert resp.status_code == 400


async def test_cannot_delete_self(auth_client):
    me = (await auth_client.get("/api/auth/me")).json()["data"]
    resp = await auth_client.delete(f"/api/users/{me['id']}")
    assert resp.status_code == 400


async def test_cannot_disable_last_admin(auth_client):
    me = (await auth_client.get("/api/auth/me")).json()["data"]
    resp = await auth_client.put(f"/api/users/{me['id']}", json={"role": "tech_query"})
    assert resp.status_code == 400


async def test_reset_password(auth_client):
    uid = await _create_user(auth_client, "reset_me", password="oldpass1")
    resp = await auth_client.post(f"/api/users/{uid}/reset-password", json={"password": "brandnew1"})
    assert resp.status_code == 200
    client = await _new_client()
    try:
        data = await _login(client, "reset_me", "brandnew1")
        assert data["user"]["username"] == "reset_me"
    finally:
        await client.aclose()


async def test_delete_user(auth_client):
    uid = await _create_user(auth_client, "del_me")
    resp = await auth_client.delete(f"/api/users/{uid}")
    assert resp.status_code == 200
    resp2 = await auth_client.get("/api/users?search=del_me")
    assert all(u["username"] != "del_me" for u in resp2.json()["data"]["list"])


# ---------- 角色管理 ----------
async def test_create_and_update_role(auth_client):
    resp = await auth_client.post(
        "/api/roles",
        json={"code": "custom_auditor", "name": "自定义审计", "description": "", "permissions": ["workspace", "audit"]},
    )
    assert resp.status_code == 200, resp.text
    rid = resp.json()["data"]["id"]
    resp = await auth_client.put(f"/api/roles/{rid}", json={"permissions": ["workspace", "audit", "reports"]})
    assert resp.status_code == 200
    assert set(resp.json()["data"]["permissions"]) == {"workspace", "audit", "reports"}


async def test_duplicate_role_code(auth_client):
    resp = await auth_client.post(
        "/api/roles", json={"code": "tech_query", "name": "重复", "permissions": []}
    )
    assert resp.status_code == 400


async def test_builtin_role_name_locked(auth_client):
    resp = await auth_client.get("/api/roles")
    rid = next(r["id"] for r in resp.json()["data"] if r["code"] == "tech_query")
    resp2 = await auth_client.put(f"/api/roles/{rid}", json={"name": "改名"})
    assert resp2.status_code == 400


async def test_builtin_role_permissions_editable(auth_client):
    resp = await auth_client.get("/api/roles")
    rid = next(r["id"] for r in resp.json()["data"] if r["code"] == "tech_query")
    resp2 = await auth_client.put(f"/api/roles/{rid}", json={"permissions": ["workspace", "audit"]})
    assert resp2.status_code == 200
    assert set(resp2.json()["data"]["permissions"]) == {"workspace", "audit"}
    # 恢复默认
    await auth_client.put(
        f"/api/roles/{rid}",
        json={"permissions": ["workspace", "sql_write", "agent", "connections", "reports", "audit"]},
    )


async def test_delete_builtin_role_forbidden(auth_client):
    resp = await auth_client.get("/api/roles")
    rid = next(r["id"] for r in resp.json()["data"] if r["code"] == "biz_query")
    resp2 = await auth_client.delete(f"/api/roles/{rid}")
    assert resp2.status_code == 400


async def test_delete_role_in_use_forbidden(auth_client):
    await _create_user(auth_client, "role_in_use_user", role="tech_manager")
    resp = await auth_client.get("/api/roles")
    rid = next(r["id"] for r in resp.json()["data"] if r["code"] == "tech_manager")
    resp2 = await auth_client.delete(f"/api/roles/{rid}")
    assert resp2.status_code == 400


async def test_assign_users_to_role(auth_client):
    uid = await _create_user(auth_client, "assign_me", role="biz_query")
    resp = await auth_client.get("/api/roles")
    rid = next(r["id"] for r in resp.json()["data"] if r["code"] == "biz_manager")
    resp2 = await auth_client.put(f"/api/roles/{rid}/users", json={"user_ids": [uid]})
    assert resp2.status_code == 200, resp2.text
    resp3 = await auth_client.get(f"/api/roles/{rid}/users")
    assert any(u["id"] == uid for u in resp3.json()["data"])
    resp4 = await auth_client.get("/api/users?search=assign_me")
    assert resp4.json()["data"]["list"][0]["role"] == "biz_manager"


async def test_assign_invalid_user(auth_client):
    resp = await auth_client.get("/api/roles")
    rid = next(r["id"] for r in resp.json()["data"] if r["code"] == "biz_manager")
    resp2 = await auth_client.put(f"/api/roles/{rid}/users", json={"user_ids": [999999]})
    assert resp2.status_code == 400


# ---------- 权限隔离 ----------
async def test_no_permission_403(auth_client):
    uid = await _create_user(auth_client, "limited_user", role="biz_query")
    client = await _new_client()
    try:
        await _login(client, "limited_user", "test1234")
        resp = await client.get("/api/users")
        assert resp.status_code == 403
        resp = await client.get("/api/roles")
        assert resp.status_code == 403
        resp = await client.get("/api/config/settings")
        assert resp.status_code == 403
        resp = await client.get("/api/audit/logs")
        assert resp.status_code == 403
        # 拥有 workspace/connections/reports 可访问
        assert (await client.get("/api/connections?page_size=5")).status_code == 200
        assert (await client.get("/api/charts")).status_code == 200
    finally:
        await client.aclose()


async def test_connections_manage_forbidden(auth_client):
    uid = await _create_user(auth_client, "conn_limited", role="tech_query")
    client = await _new_client()
    try:
        await _login(client, "conn_limited", "test1234")
        resp = await client.post("/api/connections", json={"name": "x", "db_type": "sqlite"})
        assert resp.status_code == 403
    finally:
        await client.aclose()


async def test_sql_write_permission(auth_client, demo_ds_id):
    uid = await _create_user(auth_client, "read_only_user", role="biz_query")
    client = await _new_client()
    try:
        await _login(client, "read_only_user", "test1234")
        # 只读可以
        resp = await client.post(
            "/api/sql/execute", json={"datasource_id": demo_ds_id, "sql": "SELECT COUNT(*) AS c FROM users"}
        )
        assert resp.status_code == 200
        # 写操作无权限 -> 403
        resp = await client.post(
            "/api/sql/execute", json={"datasource_id": demo_ds_id, "sql": "UPDATE orders SET status='paid' WHERE id=1"}
        )
        assert resp.status_code == 403
    finally:
        await client.aclose()


async def test_sql_ddl_permission(auth_client, demo_ds_id):
    uid = await _create_user(auth_client, "no_ddl_user", role="tech_query")
    client = await _new_client()
    try:
        await _login(client, "no_ddl_user", "test1234")
        resp = await client.post(
            "/api/sql/execute", json={"datasource_id": demo_ds_id, "sql": "CREATE TABLE tmp_denied(id INTEGER)"}
        )
        assert resp.status_code == 403
    finally:
        await client.aclose()


async def test_confirm_permission_denied(auth_client, demo_ds_id):
    uid = await _create_user(auth_client, "confirm_limited", role="biz_query")
    client = await _new_client()
    try:
        await _login(client, "confirm_limited", "test1234")
        resp = await client.post(
            "/api/sql/execute", json={"datasource_id": demo_ds_id, "sql": "UPDATE orders SET status='paid' WHERE id=1"}
        )
        assert resp.status_code == 403
    finally:
        await client.aclose()


async def test_agent_permission(auth_client):
    # 既无 agent 也无 ai_query 的角色不能访问 Agent 会话接口
    await auth_client.post(
        "/api/roles", json={"code": "no_agent_role", "name": "无Agent", "description": "t", "permissions": ["workspace"]}
    )
    uid = await _create_user(auth_client, "no_agent_user", role="no_agent_role")
    client = await _new_client()
    try:
        await _login(client, "no_agent_user", "test1234")
        resp = await client.get("/api/agent/sessions")
        assert resp.status_code == 403
    finally:
        await client.aclose()


async def test_reports_manage_forbidden(auth_client):
    uid = await _create_user(auth_client, "reports_limited", role="biz_query")
    client = await _new_client()
    try:
        await _login(client, "reports_limited", "test1234")
        resp = await client.post("/api/charts", json={"name": "x", "sql_text": "SELECT 1"})
        assert resp.status_code == 403
        resp = await client.post("/api/dashboards", json={"name": "d"})
        assert resp.status_code == 403
    finally:
        await client.aclose()