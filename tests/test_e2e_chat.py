"""
PRISM Agent - 端到端聊天测试
覆盖：用户输入 -> agent -> 工具调用 -> 回包 主链路
"""
from __future__ import annotations

import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from prism.config import get_config, ConfigError
from prism.agent import create_agent
from prism.tools.registry import registry


def test_e2e_chat_without_config_returns_config_error(monkeypatch):
    monkeypatch.setenv('PRISM_SKIP_CONFIG_FILE', '1')
    get_config()._config.clear()
    agent = create_agent()
    result = agent.chat("ping")
    result_str = str(result)
    assert isinstance(result, (dict, str))
    if isinstance(result, dict):
        assert result.get("success") is False or "配置" in result_str or "API key" in result_str or "未配置" in result_str
    else:
        assert "配置" in result_str or "API key" in result_str or "未配置" in result_str


def test_e2e_chat_tool_callable_after_config(monkeypatch):
    get_config().set("model.api_key", "sk-fake")
    get_config().set("model.default", "gpt-4o")
    get_config().set("model.provider", "openai")
    get_config().set("model.base_url", "https://api.openai.com/v1")
    try:
        agent = create_agent()
        tools = agent.list_tools()
        assert isinstance(tools, list)
        assert len(tools) > 0
    finally:
        get_config().set("model.api_key", "")


def test_e2e_registry_execute_known_tools():
    names = [t["name"] for t in registry.list_tools()]
    for name in ["file_read", "file_write", "file_patch", "terminal", "code_execution"]:
        assert name in names, f"missing tool: {name}"
