"""配置项读取测试。"""


def test_agent_limit_env_override_and_fallback(monkeypatch):
    from app.config import _agent_limit

    monkeypatch.setenv("TEST_AGENT_LIMIT", "5")
    assert _agent_limit("TEST_AGENT_LIMIT", 3) == 5

    monkeypatch.setenv("TEST_AGENT_LIMIT", "abc")
    assert _agent_limit("TEST_AGENT_LIMIT", 3) == 3

    monkeypatch.setenv("TEST_AGENT_LIMIT", "0")
    assert _agent_limit("TEST_AGENT_LIMIT", 3) == 3

    monkeypatch.setenv("TEST_AGENT_LIMIT", "999")
    assert _agent_limit("TEST_AGENT_LIMIT", 3) == 3

    monkeypatch.delenv("TEST_AGENT_LIMIT")
    assert _agent_limit("TEST_AGENT_LIMIT", 3) == 3


def test_agent_service_uses_config_limits():
    from app.config import AGENT_MAX_TOOL_ROUNDS, AGENT_SQL_MAX_ATTEMPTS
    from app.services import agent_service

    assert agent_service.AGENT_MAX_TOOL_ROUNDS == AGENT_MAX_TOOL_ROUNDS
    assert agent_service.AGENT_SQL_MAX_ATTEMPTS == AGENT_SQL_MAX_ATTEMPTS
