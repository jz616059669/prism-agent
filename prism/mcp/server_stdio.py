"""
PRISM Agent - MCP stdio Server
通过 stdin/stdout 提供标准 MCP 服务，供外部客户端直连。
"""
from __future__ import annotations

import json
import sys
from typing import Any, Dict

from prism.mcp_server import mcp_server


def serve() -> None:
    for line in sys.stdin:
        line = line.strip()
        if not line:
            continue
        try:
            payload = json.loads(line)
        except json.JSONDecodeError:
            resp = {
                "jsonrpc": "2.0",
                "id": None,
                "error": {"code": -32700, "message": "Parse error"},
            }
            print(json.dumps(resp, ensure_ascii=False), flush=True)
            continue

        if "method" not in payload:
            resp = {
                "jsonrpc": "2.0",
                "id": payload.get("id"),
                "error": {"code": -32600, "message": "Invalid Request"},
            }
            print(json.dumps(resp, ensure_ascii=False), flush=True)
            continue

        method = payload.get("method")
        if method.endswith("notification"):
            mcp_server.handle_notification(method, payload.get("params", {}))
            continue

        result = mcp_server.handle_request(payload)
        print(json.dumps(result, ensure_ascii=False), flush=True)


if __name__ == "__main__":
    serve()
