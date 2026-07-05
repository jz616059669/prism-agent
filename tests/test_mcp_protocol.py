"""
PRISM Agent - MCP 协议与 Server 测试
"""
from __future__ import annotations

import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

import json
from prism.mcp.protocol import (
    JSONRPC_VERSION,
    MCP_PROTOCOL_VERSION,
    INTERNAL_ERROR,
    INVALID_PARAMS,
    INVALID_REQUEST,
    METHOD_NOT_FOUND,
    PARSE_ERROR,
    MCPError,
    make_notification,
    make_request,
    make_response,
)
from prism.mcp_server import mcp_server


def test_protocol_constants():
    assert JSONRPC_VERSION == "2.0"
    assert MCP_PROTOCOL_VERSION == "2024-11-05"
    assert PARSE_ERROR == -32700
    assert METHOD_NOT_FOUND == -32601


def test_make_request_without_id():
    payload = make_request("initialize")
    assert payload["jsonrpc"] == "2.0"
    assert payload["method"] == "initialize"
    assert "id" not in payload


def test_make_request_with_id():
    payload = make_request("tools/list", params={}, req_id=1)
    assert payload["id"] == 1
    assert payload["params"] == {}


def test_make_response_success():
    payload = make_response(1, result={"ok": True})
    assert payload["id"] == 1
    assert payload["result"] == {"ok": True}
    assert "error" not in payload


def test_make_response_error():
    err = {"code": -32601, "message": "not found"}
    payload = make_response(1, error=err)
    assert payload["error"] == err
    assert "result" not in payload


def test_make_notification():
    payload = make_notification("initialized")
    assert payload["method"] == "initialized"
    assert "id" not in payload


def test_mcp_error_to_dict():
    err = MCPError(-32600, "bad")
    assert err.to_dict() == {"code": -32600, "message": "bad"}


def test_server_initialize():
    result = mcp_server.initialize()
    assert result["protocolVersion"] == "2024-11-05"
    assert result["serverInfo"]["name"] == "prism"


def test_server_handle_request_initialize():
    resp = mcp_server.handle_request({"jsonrpc": "2.0", "id": 1, "method": "initialize"})
    assert resp["id"] == 1
    assert resp["result"]["protocolVersion"] == "2024-11-05"


def test_server_handle_request_tools_list():
    resp = mcp_server.handle_request({"jsonrpc": "2.0", "id": 2, "method": "tools/list"})
    assert resp["id"] == 2
    tools = resp["result"]["tools"]
    assert isinstance(tools, list)
    assert any(t.get("name") == "prism_chat" for t in tools)


def test_server_handle_request_unknown_method():
    resp = mcp_server.handle_request({"jsonrpc": "2.0", "id": 3, "method": "unknown"})
    assert resp["id"] == 3
    assert resp["error"]["code"] == METHOD_NOT_FOUND


def test_server_handle_request_tool_call():
    resp = mcp_server.handle_request({
        "jsonrpc": "2.0",
        "id": 4,
        "method": "tools/call",
        "params": {"name": "prism_chat", "arguments": {"message": "hi"}},
    })
    assert resp["id"] == 4
    assert "result" in resp


def test_server_handle_notification():
    mcp_server.handle_notification("initialized", {})
    mcp_server.handle_notification("test/notify", {"x": 1})


def test_stdio_server_basic(monkeypatch, capsys):
    inputs = [
        json.dumps({"jsonrpc": "2.0", "id": 1, "method": "initialize"}) + "\n",
        json.dumps({"jsonrpc": "2.0", "id": 2, "method": "tools/list"}) + "\n",
        json.dumps({"jsonrpc": "2.0", "method": "initialized"}) + "\n",
        json.dumps({"jsonrpc": "2.0", "id": 3, "method": "unknown"}) + "\n",
        "{bad json\n",
    ]

    class FakeStdin:
        def __init__(self, lines):
            self._lines = lines
        def __iter__(self):
            return iter(self._lines)

    monkeypatch.setattr("prism.mcp.server_stdio.sys.stdin", FakeStdin(inputs))
    from prism.mcp.server_stdio import serve
    serve()
    captured = capsys.readouterr()
    assert "protocolVersion" in captured.out
    assert "tools" in captured.out
    assert "Method not found" in captured.out
    assert "Parse error" in captured.out
