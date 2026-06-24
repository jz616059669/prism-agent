"""MCP 真实 HTTP 连接测试"""

import importlib.util
import threading
import time
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from prism.mcp.http_client import MCPHTTPClient


@pytest.fixture(scope="module")
def mcp_server():
    server_path = REPO_ROOT / "tests" / "mcp_test_server.py"
    spec = importlib.util.spec_from_file_location("mcp_test_server", server_path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    server = module.run(port=0)
    host, port = server.server_address
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    base_url = f"http://{host}:{port}"
    yield base_url
    server.shutdown()
    thread.join(timeout=3)


def test_mcp_http_initialize(mcp_server):
    client = MCPHTTPClient(mcp_server)
    result = client.initialize()
    assert result.get("success") is True
    assert result.get("result", {}).get("serverInfo", {}).get("name") == "test-mcp"
    client.close()


def test_mcp_http_list_tools(mcp_server):
    client = MCPHTTPClient(mcp_server)
    result = client.list_tools()
    assert result.get("success") is True
    tools = result.get("tools", [])
    assert any(t.get("name") == "echo" for t in tools)
    client.close()


def test_mcp_http_call_tool(mcp_server):
    client = MCPHTTPClient(mcp_server)
    result = client.call_tool("echo", {"text": "hello"})
    assert result.get("success") is True
    content = result.get("result", {}).get("content", [])
    assert any("hello" in (c.get("text") or "") for c in content)
    client.close()
