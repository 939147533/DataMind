"""AI Agent 测试（使用假 LLM Provider，不依赖真实 API）。"""
import json
import re

import pytest


class FakeProvider:
    def __init__(self, config, sql="SELECT COUNT(*) AS c FROM users", answer=""):
        self.config = config
        self.sql = sql
        self.answer = answer

    async def chat(self, messages, json_mode=False):
        return json.dumps({"thought": "正在分析用户需求", "sql": self.sql, "answer": self.answer})

    async def stream(self, messages):
        for chunk in ["查询", "完成，", "共 8 位用户。"]:
            yield chunk


def _events(text: str) -> list[dict]:
    events = []
    for line in text.splitlines():
        if line.startswith("data: "):
            events.append(json.loads(line[6:]))
    return events


async def test_chat_read_sql_flow(auth_client, demo_ds_id, monkeypatch):
    monkeypatch.setattr(
        "app.services.agent_service.get_llm_provider",
        lambda cfg: FakeProvider(cfg, sql="SELECT COUNT(*) AS c FROM users"),
    )
    sess = await auth_client.post(
        "/api/agent/sessions",
        json={"datasource_id": demo_ds_id, "title": "测试对话"},
    )
    session_id = sess.json()["data"]["id"]

    resp = await auth_client.post(
        "/api/agent/chat",
        json={"session_id": session_id, "message": "统计用户数量"},
    )
    assert resp.status_code == 200
    events = _events(resp.text)
    types = [e["type"] for e in events]
    assert "thought" in types
    assert "sql" in types
    assert "result" in types
    assert "text" in types
    assert "done" in types
    result = [e for e in events if e["type"] == "result"][0]
    assert result["content"]["columns"] == ["c"]

    # 历史消息已保存
    msgs = await auth_client.get(f"/api/agent/sessions/{session_id}/messages")
    assert msgs.status_code == 200
    assert len(msgs.json()["data"]) >= 3


async def test_chat_write_sql_requires_confirm(auth_client, demo_ds_id, monkeypatch):
    monkeypatch.setattr(
        "app.services.agent_service.get_llm_provider",
        lambda cfg: FakeProvider(cfg, sql="UPDATE orders SET status='paid' WHERE id=100"),
    )
    sess = await auth_client.post("/api/agent/sessions", json={"datasource_id": demo_ds_id})
    session_id = sess.json()["data"]["id"]
    resp = await auth_client.post(
        "/api/agent/chat",
        json={"session_id": session_id, "message": "更新订单状态"},
    )
    events = _events(resp.text)
    authz = [e for e in events if e["type"] == "authorization_required"]
    assert authz, events
    assert authz[0]["risk_level"] == "warning"

    confirm = await auth_client.post(
        "/api/agent/confirm",
        json={"execution_id": authz[0]["execution_id"], "confirmed": True},
    )
    assert confirm.status_code == 200
    assert confirm.json()["data"]["status"] == "executed"


async def test_chat_no_ai_config(auth_client, demo_ds_id, monkeypatch):
    async def _none(db, session, model_config_id):
        return None

    monkeypatch.setattr("app.services.agent_service.resolve_model_config", _none)
    sess = await auth_client.post("/api/agent/sessions", json={"datasource_id": demo_ds_id})
    session_id = sess.json()["data"]["id"]
    resp = await auth_client.post(
        "/api/agent/chat",
        json={"session_id": session_id, "message": "你好"},
    )
    events = _events(resp.text)
    assert events[-1]["type"] == "done"
    assert any(e["type"] == "error" for e in events)


async def test_explain_and_optimize(auth_client, demo_ds_id, monkeypatch):
    monkeypatch.setattr(
        "app.services.agent_service.get_llm_provider",
        lambda cfg: FakeProvider(cfg),
    )
    resp = await auth_client.post(
        "/api/agent/explain",
        json={"datasource_id": demo_ds_id, "sql": "SELECT * FROM users"},
    )
    assert resp.status_code == 200
    assert "data: " in resp.text

    resp2 = await auth_client.post(
        "/api/agent/optimize",
        json={"datasource_id": demo_ds_id, "sql": "SELECT * FROM orders WHERE user_id=1"},
    )
    assert resp2.status_code == 200
    assert "data: " in resp2.text


async def test_session_lifecycle(auth_client, demo_ds_id):
    sess = await auth_client.post("/api/agent/sessions", json={"datasource_id": demo_ds_id, "title": "生命周期"})
    session_id = sess.json()["data"]["id"]
    listing = await auth_client.get("/api/agent/sessions")
    assert any(s["id"] == session_id for s in listing.json()["data"])
    dele = await auth_client.delete(f"/api/agent/sessions/{session_id}")
    assert dele.status_code == 200
