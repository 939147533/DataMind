# -*- coding: utf-8 -*-
"""AI 配置模型连通性测试端点测试。"""
import pytest
from httpx import ASGITransport, AsyncClient

from app.main import app
from app.services.llm_providers import LLMError


class FakeProvider:
    def __init__(self, ok=True, error_msg="\u6a21\u62df\u5931\u8d25"):
        self.ok = ok
        self.error_msg = error_msg

    def validate(self):
        pass

    async def ping(self):
        if not self.ok:
            raise LLMError(self.error_msg)
        return {"model": "fake-model"}


async def _new_client() -> AsyncClient:
    return AsyncClient(transport=ASGITransport(app=app), base_url="http://test")


async def test_test_ai_saved_config_success(auth_client, monkeypatch):
    monkeypatch.setattr("app.routers.system.get_llm_provider", lambda cfg: FakeProvider(ok=True))
    resp = await auth_client.post(
        "/api/config/ai", json={"provider": "openai", "api_key": "sk-test", "model_name": "gpt-x", "is_active": True}
    )
    cid = resp.json()["data"]["id"]
    resp = await auth_client.post("/api/config/ai/test", json={"config_id": cid})
    assert resp.status_code == 200, resp.text
    data = resp.json()["data"]
    assert data["success"] is True
    assert "\u8fde\u63a5\u6210\u529f" in data["message"]
    assert data["latency_ms"] >= 0
    assert data["model"] == "fake-model"


async def test_test_ai_saved_config_failure(auth_client, monkeypatch):
    monkeypatch.setattr(
        "app.routers.system.get_llm_provider",
        lambda cfg: FakeProvider(ok=False, error_msg="401 \u65e0\u6548 API Key"),
    )
    resp = await auth_client.post(
        "/api/config/ai", json={"provider": "openai", "api_key": "sk-bad", "model_name": "gpt-x"}
    )
    cid = resp.json()["data"]["id"]
    resp = await auth_client.post("/api/config/ai/test", json={"config_id": cid})
    data = resp.json()["data"]
    assert data["success"] is False
    assert "401" in data["message"]


async def test_test_ai_saved_config_missing_key(auth_client, monkeypatch):
    # 已保存但未填 Key 的配置 -> validate 抛 LLMError，返回 success=False
    def fake_get_provider(cfg):
        return FakeProvider(ok=True)

    monkeypatch.setattr("app.routers.system.get_llm_provider", fake_get_provider)
    resp = await auth_client.post(
        "/api/config/ai", json={"provider": "openai", "api_key": "", "model_name": "gpt-x"}
    )
    cid = resp.json()["data"]["id"]

    # 覆盖 get_llm_provider 让 validate 抛错：构造无 key 的 provider
    class NoKeyProvider(FakeProvider):
        def validate(self):
            raise LLMError("\u672a\u914d\u7f6e API Key\uff0c\u8bf7\u5230 \u7cfb\u7edf\u8bbe\u7f6e \u2192 AI \u914d\u7f6e \u4e2d\u586b\u5199")

    monkeypatch.setattr("app.routers.system.get_llm_provider", lambda cfg: NoKeyProvider(ok=True))
    resp = await auth_client.post("/api/config/ai/test", json={"config_id": cid})
    data = resp.json()["data"]
    assert data["success"] is False
    assert "API Key" in data["message"]


async def test_test_ai_form_params(auth_client, monkeypatch):
    monkeypatch.setattr("app.routers.system.get_llm_provider", lambda cfg: FakeProvider(ok=True))
    resp = await auth_client.post(
        "/api/config/ai/test",
        json={"provider": "openai", "api_key": "sk-form", "api_base": "https://x/v1", "model_name": "gpt-form"},
    )
    assert resp.status_code == 200, resp.text
    assert resp.json()["data"]["success"] is True


async def test_test_ai_missing_model(auth_client):
    resp = await auth_client.post("/api/config/ai/test", json={"provider": "openai", "api_key": "sk-x"})
    assert resp.status_code == 400


async def test_test_ai_not_found(auth_client):
    resp = await auth_client.post("/api/config/ai/test", json={"config_id": 999999})
    assert resp.status_code == 404


async def test_test_ai_permission(auth_client):
    await auth_client.post(
        "/api/roles", json={"code": "no_settings_role", "name": "t", "description": "t", "permissions": ["workspace"]}
    )
    await auth_client.post(
        "/api/users", json={"username": "no_settings_user", "password": "test1234", "role": "no_settings_role"}
    )
    client = await _new_client()
    await client.post("/api/auth/login", json={"username": "no_settings_user", "password": "test1234"})
    resp = await client.post("/api/config/ai/test", json={"model_name": "gpt-x"})
    assert resp.status_code == 403