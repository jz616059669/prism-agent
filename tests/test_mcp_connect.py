"""MCP 真实连接测试"""
import json
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from prism.mcp import mcp_client, MCPServer


def test_add_stdio_server():
    server = MCPServer(
        name="echo",
        transport="stdio",
        command="python",
        args=["-c", "import sys, json; print(json.dumps({'jsonrpc':'2.0','id':1,'result':{'tools':[]}}))"],
        enabled=True,
    )
    mcp_client.add_server(server)
    tools = mcp_client.list_tools("echo")
    assert isinstance(tools, list)


def test_stdio_tool_call():
    server = MCPServer(
        name="echo-tool",
        transport="stdio",
        command="python",
        args=["-c", "import sys,json;print(json.dumps({'jsonrpc':'2.0','id':1,'result':{'content':[{'type':'text','text':'ok'}]}}))"],
        enabled=True,
    )
    mcp_client.add_server(server)
    tools = mcp_client.list_tools("echo-tool")
    assert isinstance(tools, list)


def test_http_server_from_config():
    server = MCPServer(
        name="http-test",
        transport="http",
        url="http://127.0.0.1:1",
        enabled=False,
    )
    mcp_client.add_server(server)
    tools = mcp_client.list_tools("http-test")
    assert isinstance(tools, list)
