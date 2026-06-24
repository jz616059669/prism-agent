"""
最小本地 MCP HTTP 测试服务器
仅用于测试 prism.mcp.http_client 的真实 HTTP 连接
"""

import json
from http.server import HTTPServer, BaseHTTPRequestHandler


class MCPHandler(BaseHTTPRequestHandler):
    def do_POST(self):
        length = int(self.headers.get("Content-Length", 0))
        body = self.rfile.read(length).decode("utf-8")
        payload = json.loads(body)

        method = payload.get("method")
        req_id = payload.get("id")

        if method == "initialize":
            result = {
                "protocolVersion": "2024-11-05",
                "capabilities": {"tools": {}},
                "serverInfo": {"name": "test-mcp", "version": "0.0.0"},
            }
        elif method == "tools/list":
            result = {
                "tools": [
                    {
                        "name": "echo",
                        "description": "echo tool",
                        "inputSchema": {"type": "object", "properties": {"text": {"type": "string"}}},
                    }
                ]
            }
        elif method == "tools/call":
            name = payload.get("params", {}).get("name")
            arguments = payload.get("params", {}).get("arguments", {})
            result = {
                "content": [{"type": "text", "text": json.dumps({"tool": name, "args": arguments})}]
            }
        else:
            result = {"error": {"code": -32601, "message": f"Method not found: {method}"}}

        response = {"jsonrpc": "2.0", "id": req_id, "result": result}
        data = json.dumps(response).encode("utf-8")

        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def log_message(self, format, *args):
        # 关闭默认日志
        pass


def run(host="127.0.0.1", port=0):
    server = HTTPServer((host, port), MCPHandler)
    print(f"MCP test server running on {server.server_address}")
    return server
