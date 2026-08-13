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


class ChartProvider(FakeProvider):
    def __init__(self, config, sql="SELECT 1 AS x"):
        super().__init__(config, sql=sql)
        self.chart = {"type": "line", "title": "交易趋势", "x_column": "month", "y_column": "total", "aggregation": "sum"}

    async def chat(self, messages, json_mode=False):
        return json.dumps({"thought": "分析", "sql": self.sql, "answer": "", "chart": self.chart})


async def test_chat_chart_persists_result(auth_client, demo_ds_id, monkeypatch):
    sql = "SELECT strftime('%Y-%m', created_at) AS month, SUM(amount) AS total FROM orders GROUP BY month ORDER BY month"
    monkeypatch.setattr(
        "app.services.agent_service.get_llm_provider",
        lambda cfg: ChartProvider(cfg, sql=sql),
    )
    sess = await auth_client.post("/api/agent/sessions", json={"datasource_id": demo_ds_id})
    session_id = sess.json()["data"]["id"]
    resp = await auth_client.post(
        "/api/agent/chat",
        json={"session_id": session_id, "message": "按月份统计交易趋势并生成图表"},
    )
    assert resp.status_code == 200
    events = _events(resp.text)
    charts = [e for e in events if e["type"] == "chart"]
    assert charts, [e["type"] for e in events]
    assert charts[0]["content"]["chart_type"] == "line"

    msgs = await auth_client.get(f"/api/agent/sessions/{session_id}/messages")
    chart_msgs = [m for m in msgs.json()["data"] if m["message_type"] == "chart"]
    assert chart_msgs, [m["message_type"] for m in msgs.json()["data"]]
    payload = json.loads(chart_msgs[0]["content"])
    assert payload["chart"]["chart_type"] == "line"
    assert payload["result"]["columns"] == ["month", "total"]
    assert payload["result"]["rows"]
    assert payload["result"]["sql_text"] == sql

def test_parse_chart_multiple_y_columns():
    from app.services.agent_service import _parse_chart

    cfg = _parse_chart(
        {
            "type": "line",
            "title": "近30天交易趋势",
            "x_column": "TRANS_DATE",
            "y_columns": ["TRANS_COUNT", "TRANS_AMOUNT"],
            "aggregation": "none",
        }
    )
    assert cfg is not None
    assert cfg["chart_type"] == "line"
    assert cfg["x_column"] == "TRANS_DATE"
    assert cfg["y_column"] == "TRANS_COUNT, TRANS_AMOUNT"

    # 旧格式单 y_column 兼容
    cfg2 = _parse_chart({"type": "bar", "title": "t", "x_column": "DAY", "y_column": "COUNT"})
    assert cfg2["y_column"] == "COUNT"

    # 逗号分隔的 y_column 兼容
    cfg3 = _parse_chart({"type": "bar", "title": "t", "x_column": "DAY", "y_column": "A, B"})
    assert cfg3["y_column"] == "A, B"

    # 非法：无 y 列 / 空数组 / 未知类型
    assert _parse_chart({"type": "pie", "x_column": "DAY"}) is None
    assert _parse_chart({"type": "line", "x_column": "DAY", "y_columns": []}) is None
    assert _parse_chart({"type": "radar", "x_column": "DAY", "y_column": "C"}) is None


def test_schema_summary_enum_hint():
    from app.adapters.base import ConnectionInfo
    from app.adapters.sqlite_adapter import SQLiteAdapter

    adapter = SQLiteAdapter(ConnectionInfo(db_type="sqlite", database_name="demo.db"))
    summary = adapter.schema_summary()
    assert "orders(" in summary
    assert "[枚举:" in summary
    assert any(k in summary for k in ("pending", "paid", "done", "shipped"))
