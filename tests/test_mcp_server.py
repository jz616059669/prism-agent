"""
PRISM Agent - MCP Server tests
"""
from __future__ import annotations

import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from prism.mcp_server import PrismMCPServer


def test_list_tools():
    server = PrismMCPServer()
    tools = server.list_tools()
    names = [tool.get("name") for tool in tools]
    assert "prism_chat" in names
    assert "prism_search" in names
    assert "prism_execute" in names
    assert "prism_remember" in names
    assert "prism_recall" in names


def test_call_tool_search(monkeypatch):
    server = PrismMCPServer()
    calls = {"count": 0}

    def fake_handler(query=None, max_results=5):
        calls["count"] += 1
        return {"success": True, "results": [{"title": "x", "url": "http://example.com"}]}

    monkeypatch.setattr("prism.tools.registry.registry.execute", lambda name, **kwargs: fake_handler(query=kwargs.get("query")))
    result = server.call_tool("prism_search", {"query": "hello"})
    assert result.get("success") is True


def test_call_tool_execute(monkeypatch):
    server = PrismMCPServer()
    monkeypatch.setattr("prism.tools.registry.registry.execute", lambda name, **kwargs: {"success": True, "output": "ok"})
    result = server.call_tool("prism_execute", {"code": "print(1)"})
    assert result.get("success") is True


def test_call_unknown_tool():
    server = PrismMCPServer()
    result = server.call_tool("prism_does_not_exist", {})
    assert "error" in result
