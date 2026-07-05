"""
PRISM Agent - MCP JSON-RPC 2.0 基础
统一错误码与协议常量。
"""
from __future__ import annotations

# JSON-RPC 2.0
JSONRPC_VERSION = "2.0"

# MCP 2024-11-05
MCP_PROTOCOL_VERSION = "2024-11-05"

# 标准错误码
PARSE_ERROR = -32700
INVALID_REQUEST = -32600
METHOD_NOT_FOUND = -32601
INVALID_PARAMS = -32602
INTERNAL_ERROR = -32603


class MCPError(Exception):
    def __init__(self, code: int, message: str, data: Any = None):
        self.code = code
        self.message = message
        self.data = data
        super().__init__(message)

    def to_dict(self) -> Dict[str, Any]:
        err = {"code": self.code, "message": self.message}
        if self.data is not None:
            err["data"] = self.data
        return err


def make_request(method: str, params: Any = None, req_id: Any = None) -> Dict[str, Any]:
    payload: Dict[str, Any] = {"jsonrpc": JSONRPC_VERSION, "method": method}
    if params is not None:
        payload["params"] = params
    if req_id is not None:
        payload["id"] = req_id
    return payload


def make_response(req_id: Any, result: Any = None, error: Any = None) -> Dict[str, Any]:
    payload: Dict[str, Any] = {"jsonrpc": JSONRPC_VERSION, "id": req_id}
    if error is not None:
        payload["error"] = error
    else:
        payload["result"] = result
    return payload


def make_notification(method: str, params: Any = None) -> Dict[str, Any]:
    payload: Dict[str, Any] = {"jsonrpc": JSONRPC_VERSION, "method": method}
    if params is not None:
        payload["params"] = params
    return payload
