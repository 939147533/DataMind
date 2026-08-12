# -*- coding: utf-8 -*-
"""智能查询（ai_query）权限、Agent 图表事件与保存图表测试。"""
import json

import pytest
from httpx import ASGITransport, AsyncClient

from app.main import app


class FakeProvider:
    def __init__(self, config, sql="SELECT status, COUNT(*) AS cnt FROM orders GROUP BY status", chart=None):
        self.config = config
        self.sql = sql
        self.chart = chart

    async def chat(self, messages, json_mode=False):
        payload = {"thought": "正在分析需求", "sql": self.sql, "answer": ""}
        if self.chart is not None:
            payload["chart"] = self.chart
        return json.dumps(payload)

    async def stream(self, messages):
        for chunk in ["汇总", "完成。"]:
            yield chunk


def _events(text: str) -> list[dict]:
    return [json.loads(line[6:]) for line in text.splitlines() if line.startswith("data: ")]


async def _new_client() -> AsyncClient:
    return AsyncClient(transport=ASGITransport(app=app), base_url="http://test")


async def _create_role(auth_client, code, permissions):
    resp = await auth_client.post(
        "/api/roles", json={"code": code, "name": code, "description": "test", "permissions": permissions}
    )
    assert resp.status_code == 200, resp.text
    return resp.json()["data"]["id"]


async def _create_user(auth_client, username, role):
    resp = await auth_client.post(
        "/api/users",
        json={"username": username, "password": "test1234", "display_name": username, "role": role, "is_active": True},
    )
    assert resp.status_code == 200, resp.text
    return resp.json()["data"]["id"]


async def _chat(client, session_id, message="统计各状态订单数量"):
    resp = await client.post("/api/agent/chat", json={"session_id": session_id, "message": message})
    assert resp.status_code == 200, resp.text
    return _events(resp.text)


# ---------- 角色默认权限 ----------
async def test_builtin_roles_include_ai_query_and_keep_workspace(auth_client):
    resp = await auth_client.get("/api/roles")
    roles = {r["code"]: r["permissions"] for r in resp.json()["data"]}
    for code in ("tech_manager", "tech_query", "biz_manager", "biz_query"):
        assert "ai_query" in roles[code], code
        assert "workspace" in roles[code], "业务/技术角色默认不应被写死去掉 workspace: " + code


# ---------- ai_query 用户可走 Agent 只读流程 ----------
async def test_ai_query_only_user_agent_read_flow(auth_client, demo_ds_id, monkeypatch):
    await _create_role(auth_client, "ai_only", ["ai_query"])
    uid = await _create_user(auth_client, "ai_only_user", "ai_only")
    assert uid > 0
    client = await _new_client()
    await client.post("/api/auth/login", json={"username": "ai_only_user", "password": "test1234"})

    sess = await client.post("/api/agent/sessions", json={"datasource_id": demo_ds_id})
    assert sess.status_code == 200, sess.text
    session_id = sess.json()["data"]["id"]

    monkeypatch.setattr(
        "app.services.agent_service.get_llm_provider",
        lambda cfg: FakeProvider(cfg),
    )
    events = await _chat(client, session_id)
    types = [e["type"] for e in events]
    assert "thought" in types and "sql" in types and "result" in types and "done" in types

    # 历史包含 SQL 与文本
    msgs = await client.get(f"/api/agent/sessions/{session_id}/messages")
    assert msgs.status_code == 200
    assert len(msgs.json()["data"]) >= 3


async def test_ai_query_user_cannot_confirm_explain_optimize(auth_client, demo_ds_id):
    await _create_role(auth_client, "ai_only2", ["ai_query"])
    await _create_user(auth_client, "ai_only_user2", "ai_only2")
    client = await _new_client()
    await client.post("/api/auth/login", json={"username": "ai_only_user2", "password": "test1234"})
    assert (await client.post("/api/agent/confirm", json={"execution_id": "x", "confirmed": True})).status_code == 403
    assert (await client.post("/api/agent/explain", json={"datasource_id": demo_ds_id, "sql": "SELECT 1"})).status_code == 403
    assert (await client.post("/api/agent/optimize", json={"datasource_id": demo_ds_id, "sql": "SELECT 1"})).status_code == 403


async def test_ai_query_user_dml_and_ddl_rejected(auth_client, demo_ds_id, monkeypatch):
    await _create_role(auth_client, "ai_only3", ["ai_query"])
    await _create_user(auth_client, "ai_only_user3", "ai_only3")
    client = await _new_client()
    await client.post("/api/auth/login", json={"username": "ai_only_user3", "password": "test1234"})
    sess = await client.post("/api/agent/sessions", json={"datasource_id": demo_ds_id})
    session_id = sess.json()["data"]["id"]

    monkeypatch.setattr(
        "app.services.agent_service.get_llm_provider",
        lambda cfg: FakeProvider(cfg, sql="DELETE FROM users WHERE id = 99999"),
    )
    events = await _chat(client, session_id, "删除一个用户")
    types = [e["type"] for e in events]
    assert "error" in types, types
    assert "done" in types
    assert any("\u65e0\u6743\u9650" in str(e.get("content", "")) for e in events if e["type"] == "error")


# ---------- Agent 图表事件 ----------
async def test_agent_chart_event(auth_client, demo_ds_id, monkeypatch):
    chart_cfg = {"type": "bar", "title": "订单状态分布", "x_column": "status", "y_column": "cnt", "aggregation": "count"}
    monkeypatch.setattr(
        "app.services.agent_service.get_llm_provider",
        lambda cfg: FakeProvider(cfg, chart=chart_cfg),
    )
    sess = await auth_client.post("/api/agent/sessions", json={"datasource_id": demo_ds_id})
    session_id = sess.json()["data"]["id"]
    events = await _chat(auth_client, session_id)
    types = [e["type"] for e in events]
    assert "chart" in types, types
    chart = [e for e in events if e["type"] == "chart"][0]
    assert chart["content"]["chart_type"] == "bar"
    assert chart["content"]["x_column"] == "status"

    # 历史消息包含 chart 类型
    msgs = await auth_client.get(f"/api/agent/sessions/{session_id}/messages")
    assert any(m["message_type"] == "chart" for m in msgs.json()["data"])


async def test_invalid_chart_config_ignored(auth_client, demo_ds_id, monkeypatch):
    monkeypatch.setattr(
        "app.services.agent_service.get_llm_provider",
        lambda cfg: FakeProvider(cfg, chart={"type": "scatter", "title": "x", "x_column": "a", "y_column": "b"}),
    )
    sess = await auth_client.post("/api/agent/sessions", json={"datasource_id": demo_ds_id})
    session_id = sess.json()["data"]["id"]
    events = await _chat(auth_client, session_id)
    assert "chart" not in [e["type"] for e in events]


# ---------- 保存图表 ----------
async def test_save_agent_chart(auth_client, demo_ds_id):
    resp = await auth_client.post(
        "/api/agent/charts",
        json={
            "name": "Agent 生成图表",
            "datasource_id": demo_ds_id,
            "sql_text": "SELECT status, COUNT(*) AS cnt FROM orders GROUP BY status",
            "chart_type": "pie",
            "x_column": "status",
            "y_column": "cnt",
            "aggregation": "count",
        },
    )
    assert resp.status_code == 200, resp.text
    chart = resp.json()["data"]
    assert chart["id"] > 0 and chart["chart_type"] == "pie"
    charts = await auth_client.get("/api/charts")
    assert any(c["id"] == chart["id"] for c in charts.json()["data"])


async def test_save_agent_chart_permission(auth_client, demo_ds_id):
    # 仅报表查看权限（无 ai_query / reports_manage）不能保存图表
    await _create_role(auth_client, "reports_viewer", ["reports"])
    await _create_user(auth_client, "reports_viewer_user", "reports_viewer")
    client = await _new_client()
    await client.post("/api/auth/login", json={"username": "reports_viewer_user", "password": "test1234"})
    resp = await client.post(
        "/api/agent/charts",
        json={"name": "x", "datasource_id": demo_ds_id, "chart_type": "bar", "x_column": "a", "y_column": "b"},
    )
    assert resp.status_code == 403


# ---------- 导出 ----------
async def test_ai_query_user_can_export_result(auth_client, demo_ds_id):
    await _create_role(auth_client, "ai_only4", ["ai_query"])
    await _create_user(auth_client, "ai_only_user4", "ai_only4")
    client = await _new_client()
    await client.post("/api/auth/login", json={"username": "ai_only_user4", "password": "test1234"})
    resp = await client.post(
        "/api/export/result?format=csv",
        json={"datasource_id": demo_ds_id, "sql": "SELECT COUNT(*) AS c FROM users"},
    )
    assert resp.status_code == 200, resp.text
    # 导出接口拒绝非只读
    resp = await client.post(
        "/api/export/result?format=csv",
        json={"datasource_id": demo_ds_id, "sql": "DELETE FROM users WHERE id = 99999"},
    )
    assert resp.status_code == 400