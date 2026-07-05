"""
PRISM Agent - tests for MCP tool routing and tool listing
"""
from __future__ import annotations

import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

import pytest

from prism.agent import Agent


class FakeMCPClient:
    def __init__(self):
        self.calls = []
        self.tools = {
            "srv": [
                {
                    "name": "mcp_search",
                    "description": "Search via MCP",
                    "inputSchema": {"type": "object", "properties": {"q": {"type": "string"}}},
                }
            ]
        }

    def list_tools(self, server_name=None):
        if server_name:
            return self.tools.get(server_name, [])
        result = []
        for tools in self.tools.values():
            result.extend(tools)
        return result

    def call_tool(self, server_name, tool_name, arguments):
        self.calls.append((server_name, tool_name, arguments))
        return {"success": True, "result": {"ok": True}}


def test_agent_execute_local_tool_fallback(monkeypatch):
    agent = Agent()
    result = agent.execute_tool("file_read", path="prism/agent.py", offset=1, limit=5)
    assert result.get("success") is True


def test_agent_list_tools_includes_mcp_tools(monkeypatch):
    fake = FakeMCPClient()
    monkeypatch.setattr("prism.agent.mcp_client", fake, raising=False)
    agent = Agent()
    tools = agent.list_tools()
    names = [t.get("name") for t in tools]
    assert "mcp_search" in names
    assert any(t.get("source") == "mcp" for t in tools)


def test_agent_execute_mcp_tool_routes(monkeypatch):
    fake = FakeMCPClient()
    monkeypatch.setattr("prism.agent.mcp_client", fake, raising=False)
    agent = Agent()
    result = agent.execute_tool("mcp_search", q="hello")
    assert result.get("success") is True
    assert fake.calls == [("srv", "mcp_search", {"q": "hello"})]
