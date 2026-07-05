"""
PRISM Agent - 集成测试
覆盖：配置 -> 提供商 -> Agent -> 浏览器基础流程
"""

import os
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from prism.config import get_config, ConfigError
from prism.providers.manager import provider_pool, ProviderPool
from prism.agent import create_agent
from prism.tools.browser_bridge import open_page, page_snapshot, close_browser


def test_config_validation_fails_without_api_key():
    with pytest.raises(ConfigError):
        get_config().set("model.api_key", "")
        get_config().validate()


def test_provider_pool_requires_key():
    pool = ProviderPool()
    result = pool.chat([{"role": "user", "content": "ping"}])
    assert result["success"] is False
    assert "api_key" in result["error"] or "未配置" in result["error"]


def test_agent_creation_uses_config():
    get_config().set("model.api_key", "sk-fake")
    get_config().set("model.default", "gpt-4o")
    get_config().set("model.provider", "openai")
    get_config().set("model.base_url", "https://api.openai.com/v1")
    try:
        agent = create_agent()
        assert agent is not None
        tools = agent.list_tools()
        assert isinstance(tools, list)
    finally:
        get_config().set("model.api_key", "")


def test_browser_open_and_snapshot():
    result = open_page("https://example.com", headless=True)
    assert result["success"] is True
    assert "example.com" in result.get("url", "")

    snap = page_snapshot()
    assert snap["success"] is True
    assert "Example Domain" in snap.get("title", "") or "Example Domain" in snap.get("content", "")

    close = close_browser()
    assert close["success"] is True
