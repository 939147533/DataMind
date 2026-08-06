"""认证测试。"""
import pytest


async def test_login_success(auth_client):
    resp = await auth_client.get("/api/auth/me")
    assert resp.status_code == 200
    data = resp.json()["data"]
    assert data["username"] == "admin"


async def test_login_wrong_password(client):
    resp = await client.post("/api/auth/login", json={"username": "admin", "password": "wrong"})
    assert resp.status_code == 401


async def test_me_requires_auth(client):
    resp = await client.get("/api/auth/me")
    assert resp.status_code == 401


async def test_logout(auth_client):
    resp = await auth_client.post("/api/auth/logout")
    assert resp.status_code == 200
    resp2 = await auth_client.get("/api/auth/me")
    assert resp2.status_code == 401
