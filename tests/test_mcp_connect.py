"""MCP 真实连接测试"""
import pytest

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
