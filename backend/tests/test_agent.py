"""AI Agent 测试（使用假 LLM Provider，不依赖真实 API）。"""
import json



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


class ScriptedProvider:
    """按调用次序返回不同 SQL，用于验证失败修正重试。"""

    def __init__(self, config, scripts):
        self.config = config
        self.scripts = list(scripts)
        self.calls = 0

    async def chat(self, messages, json_mode=False):
        sql = self.scripts[min(self.calls, len(self.scripts) - 1)]
        self.calls += 1
        return json.dumps({"thought": "分析中", "sql": sql, "answer": ""})

    async def stream(self, messages):
        yield "查询完成。"


async def test_read_sql_failure_triggers_fix_retry(auth_client, demo_ds_id, monkeypatch):
    """READ 查询本身报错（400）时，应把错误回传给模型修正并重试。"""
    provider = ScriptedProvider(
        None,
        ["SELECT * FROM no_such_table_xyz LIMIT 1", "SELECT COUNT(*) AS c FROM users"],
    )
    monkeypatch.setattr("app.services.agent_service.get_llm_provider", lambda cfg: provider)
    sess = await auth_client.post("/api/agent/sessions", json={"datasource_id": demo_ds_id})
    session_id = sess.json()["data"]["id"]

    resp = await auth_client.post(
        "/api/agent/chat",
        json={"session_id": session_id, "message": "统计用户数量"},
    )
    assert resp.status_code == 200
    events = _events(resp.text)
    types = [e["type"] for e in events]
    assert "retry" in types, types
    assert "result" in types, types
    assert provider.calls == 2  # 首次生成 + 一次修正
    sqls = [e["content"] for e in events if e["type"] == "sql"]
    assert sqls[-1] == "SELECT COUNT(*) AS c FROM users"


async def test_sql_retry_limit_is_configurable(auth_client, demo_ds_id, monkeypatch):
    """修正次数上限取自 config：1 表示失败即终止，2 表示只给一次修正机会。"""
    for limit, expected_calls, expect_retry in ((1, 1, False), (2, 2, True)):
        provider = ScriptedProvider(None, ["SELECT * FROM no_such_table_xyz LIMIT 1"])
        monkeypatch.setattr("app.services.agent_service.get_llm_provider", lambda cfg, p=provider: p)
        monkeypatch.setattr("app.services.agent_service.AGENT_SQL_MAX_ATTEMPTS", limit)

        sess = await auth_client.post("/api/agent/sessions", json={"datasource_id": demo_ds_id})
        session_id = sess.json()["data"]["id"]
        resp = await auth_client.post(
            "/api/agent/chat",
            json={"session_id": session_id, "message": "统计用户数量"},
        )
        assert resp.status_code == 200
        types = [e["type"] for e in _events(resp.text)]
        assert provider.calls == expected_calls, (limit, types)
        assert ("retry" in types) is expect_retry, (limit, types)
        assert "error" in types and "done" in types


class ChartThenFixProvider:
    """首轮带 chart 配置但 SQL 必然报错；修正轮只返回 SQL（不带 chart）。"""

    def __init__(self, config):
        self.config = config
        self.calls = 0

    async def chat(self, messages, json_mode=False):
        self.calls += 1
        if self.calls == 1:
            return json.dumps(
                {
                    "thought": "按用户数统计",
                    "sql": "SELECT * FROM no_such_table_xyz LIMIT 1",
                    "answer": "",
                    "chart": {"type": "bar", "title": "用户数", "x_column": "c", "y_columns": ["c"]},
                }
            )
        return json.dumps({"thought": "已修正", "sql": "SELECT COUNT(*) AS c FROM users", "answer": ""})

    async def stream(self, messages):
        yield "查询完成。"


async def test_chart_survives_sql_fix_retry(auth_client, demo_ds_id, monkeypatch):
    """F1：SQL 自动修正后图表配置不能丢（chart 必须在修正循环之前解析）。"""
    provider = ChartThenFixProvider(None)
    monkeypatch.setattr("app.services.agent_service.get_llm_provider", lambda cfg: provider)
    sess = await auth_client.post("/api/agent/sessions", json={"datasource_id": demo_ds_id})
    session_id = sess.json()["data"]["id"]

    resp = await auth_client.post(
        "/api/agent/chat",
        json={"session_id": session_id, "message": "统计用户数量并画图"},
    )
    assert resp.status_code == 200
    events = _events(resp.text)
    types = [e["type"] for e in events]
    assert "retry" in types, types
    assert "chart" in types, types
    chart = [e for e in events if e["type"] == "chart"][0]["content"]
    assert chart["chart_type"] == "bar"
    assert chart["x_column"] == "c"


async def test_history_isolated_after_datasource_switch(auth_client, demo_ds_id):
    """A1：会话内切换数据源后，历史上下文不再包含切换前的 SQL（避免方言串味）。"""
    from app.database import SessionLocal
    from app.models import AgentMessage
    from app.services import agent_service

    sess = await auth_client.post("/api/agent/sessions", json={"datasource_id": demo_ds_id})
    session_id = sess.json()["data"]["id"]

    async with SessionLocal() as db:
        db.add(AgentMessage(session_id=session_id, role="user", content="看下订单", message_type="text"))
        db.add(
            AgentMessage(
                session_id=session_id,
                role="assistant",
                content="SELECT * FROM orders LIMIT 5",
                message_type="sql",
            )
        )
        await db.commit()
        assert len(await agent_service._load_history(db, session_id)) == 2

        await agent_service.switch_session_datasource(db, session_id, None)
        assert await agent_service._load_history(db, session_id) == []

        # 切换后的新消息仍进入上下文
        db.add(AgentMessage(session_id=session_id, role="user", content="换个库再问", message_type="text"))
        await db.commit()
        history = await agent_service._load_history(db, session_id)
        assert [h["content"] for h in history] == ["换个库再问"]
