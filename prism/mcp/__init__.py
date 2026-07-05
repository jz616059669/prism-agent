"""
PRISM Agent - MCP (Model Context Protocol) 支持
整合 Hermes 的 MCP 客户端能力
支持 stdio 和 HTTP 两种传输模式
"""

import json
import subprocess
import threading
import time
from typing import Dict, Any, Optional, List
from dataclasses import dataclass
from pathlib import Path

from prism.logging import logger
import traceback

try:
    from prism.mcp.http_client import MCPHTTPClient
    _HTTP_CLIENT_AVAILABLE = True
except Exception:
    _HTTP_CLIENT_AVAILABLE = False
    logger.debug("HTTP client import failed: %s", traceback.format_exc())


@dataclass
class MCPServer:
    """MCP 服务器配置"""
    name: str
    transport: str  # stdio | http | sse
    command: Optional[str] = None  # stdio 模式：启动命令
    url: Optional[str] = None  # http/sse 模式：服务器地址
    args: List[str] = None  # stdio 模式：参数
    enabled: bool = True
    env: Optional[Dict[str, str]] = None  # stdio 模式：环境变量

    def __post_init__(self):
        if self.args is None:
            self.args = []
        if self.env is None:
            self.env = {}


class MCPClient:
    """
    MCP 客户端
    支持：
    - stdio：启动子进程通信
    - http/sse：HTTP 长连接
    """

    def __init__(self):
        self.servers: Dict[str, MCPServer] = {}
        self.processes: Dict[str, subprocess.Popen] = {}
        self.tools: Dict[str, Dict[str, Any]] = {}
        self.http_clients: Dict[str, MCPHTTPClient] = {}
        self._stdio_initialized: Dict[str, bool] = {}
        self._stdio_locks: Dict[str, threading.Lock] = {}

    def add_server(self, server: MCPServer):
        """添加 MCP 服务器"""
        self.servers[server.name] = server
        if server.enabled:
            self._connect_server(server)

    def _connect_server(self, server: MCPServer):
        """连接到 MCP 服务器"""
        if server.transport == "stdio":
            self._connect_stdio(server)
        elif server.transport == "http":
            self._connect_http(server)
        elif server.transport == "sse":
            self._connect_sse(server)

    def _connect_stdio(self, server: MCPServer):
        """通过 stdio 连接并完成 MCP 握手"""
        try:
            env = os.environ.copy()
            if server.env:
                env.update(server.env)
            process = subprocess.Popen(
                [server.command] + server.args,
                stdin=subprocess.PIPE,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                bufsize=1,
                env=env,
            )
            self.processes[server.name] = process
            self._stdio_initialized[server.name] = False
            self._stdio_locks.setdefault(server.name, threading.Lock())
            print(f"[MCP] 已连接 stdio 服务器: {server.name}")
            self._initialize_stdio(server, process)
        except Exception as e:
            print(f"[MCP] 连接失败 {server.name}: {e}")

    def _initialize_stdio(self, server: MCPServer, process: subprocess.Popen):
        """发送 MCP initialize 握手并等待 initialized"""
        if self._stdio_initialized.get(server.name):
            return
        lock = self._stdio_locks.setdefault(server.name, threading.Lock())
        with lock:
            if self._stdio_initialized.get(server.name):
                return
            try:
                init_request = {
                    "jsonrpc": "2.0",
                    "id": 1,
                    "method": "initialize",
                    "params": {
                        "protocolVersion": "2024-11-05",
                        "capabilities": {},
                        "clientInfo": {"name": "prism", "version": "2.1.2"},
                    },
                }
                request_str = json.dumps(init_request, ensure_ascii=False) + "\n"
                process.stdin.write(request_str)
                process.stdin.flush()

                response = self._read_stdio_response(process, timeout=5.0)
                if response and "result" in response:
                    self._stdio_initialized[server.name] = True
                    notify = {"jsonrpc": "2.0", "method": "notifications/initialized"}
                    process.stdin.write(json.dumps(notify, ensure_ascii=False) + "\n")
                    process.stdin.flush()
                    print(f"[MCP] stdio 服务器初始化成功: {server.name}")
                else:
                    # 宽松处理：部分简易 server 不遵循完整握手
                    self._stdio_initialized[server.name] = True
                    print(f"[MCP] stdio 服务器 {server.name} 未返回有效初始化响应，仍允许调用")
            except Exception as e:
                self._stdio_initialized[server.name] = True
                print(f"[MCP] stdio 初始化失败 {server.name}: {e}")

    def _read_stdio_response(self, process: subprocess.Popen, timeout: float = 5.0) -> Optional[Dict[str, Any]]:
        """读取 stdio 单行 JSON，跳过通知，返回首个带 result/error 的响应"""
        start = time.time()
        while time.time() - start < timeout:
            try:
                line = process.stdout.readline()
            except Exception:
                logger.debug("read stdio line failed: %s", traceback.format_exc())
                return None
            if not line:
                return None
            line = line.strip()
            if not line:
                continue
            try:
                response = json.loads(line)
                if "id" not in response and "method" in response:
                    continue
                return response
            except (json.JSONDecodeError, ValueError):
                continue
        return None

    def _connect_http(self, server: MCPServer):
        """通过 HTTP/SSE 连接"""
        if not _HTTP_CLIENT_AVAILABLE or not server.url:
            print(f"[MCP] HTTP 服务器 {server.name} 不可用: {server.url}")
            return

        client = MCPHTTPClient(server.url)
        init = client.initialize()
        if init.get('success'):
            self.http_clients[server.name] = client
            print(f"[MCP] 已连接 HTTP 服务器: {server.name}")
        else:
            print(f"[MCP] HTTP 服务器 {server.name} 初始化失败: {init.get('error')}")

    def _connect_sse(self, server: MCPServer):
        """通过 SSE 连接（流式）"""
        if not _HTTP_CLIENT_AVAILABLE or not server.url:
            print(f"[MCP] SSE 服务器 {server.name} 不可用: {server.url}")
            return
        try:
            from prism.mcp.sse_client import MCPSSEClient
            client = MCPSSEClient(server.url)
            init = client.initialize()
            if init.get('success'):
                self.http_clients[server.name] = client
                print(f"[MCP] 已连接 SSE 服务器: {server.name}")
            else:
                print(f"[MCP] SSE 服务器 {server.name} 初始化失败: {init.get('error')}")
        except Exception as e:
            print(f"[MCP] SSE 连接失败 {server.name}: {e}")

    def list_tools(self, server_name: Optional[str] = None) -> List[Dict[str, Any]]:
        """
        列出可用工具

        Args:
            server_name: 指定服务器名，None 表示所有服务器
        """
        servers = [server_name] if server_name else list(self.servers.keys())
        tools = []
        for name in servers:
            self._refresh_tools(name)
            tools.extend(self.tools.get(name, []))
        return tools

    def _refresh_tools(self, server_name: str):
        if server_name not in self.servers:
            return
        if server_name in self.tools:
            return
        server = self.servers[server_name]
        discovered = []
        if server.transport == "stdio":
            discovered = self._list_stdio_tools(server_name)
        elif server.transport == "http":
            discovered = self._list_http_tools(server_name)
        elif server.transport == "sse":
            discovered = self._list_sse_tools(server_name)
        self.tools[server_name] = discovered

    def call_tool(self, server_name: str, tool_name: str, arguments: Dict[str, Any]) -> Dict[str, Any]:
        """
        调用 MCP 工具

        Args:
            server_name: 服务器名
            tool_name: 工具名
            arguments: 参数
        """
        server = self.servers.get(server_name)
        if not server:
            return {'success': False, 'error': f'Server not found: {server_name}'}

        if server.transport == "stdio":
            return self._call_stdio_tool(server, tool_name, arguments)
        elif server.transport == "http":
            return self._call_http_tool(server_name, tool_name, arguments)
        elif server.transport == "sse":
            return self._call_sse_tool(server_name, tool_name, arguments)
        else:
            return {'success': False, 'error': f'Unsupported transport: {server.transport}'}

    def _call_stdio_tool(self, server: MCPServer, tool_name: str, arguments: Dict[str, Any]) -> Dict[str, Any]:
        """通过 stdio 调用工具"""
        process = self.processes.get(server.name)
        if not process:
            return {'success': False, 'error': f'Server {server.name} not connected'}

        try:
            if not self._stdio_initialized.get(server.name):
                self._initialize_stdio(server, process)

            request = {
                "jsonrpc": "2.0",
                "id": 2,
                "method": "tools/call",
                "params": {
                    "name": tool_name,
                    "arguments": arguments,
                },
            }

            request_str = json.dumps(request, ensure_ascii=False) + "\n"
            process.stdin.write(request_str)
            process.stdin.flush()

            response = self._read_stdio_response(process, timeout=30.0)
            if not response:
                return {'success': False, 'error': 'No response from server'}

            if "result" in response:
                return {
                    'success': True,
                    'result': response["result"],
                }
            elif "error" in response:
                return {
                    'success': False,
                    'error': response["error"].get("message", "Unknown error"),
                }
            else:
                return {'success': False, 'error': 'Invalid response'}

        except Exception as e:
            return {'success': False, 'error': str(e)}

    def _call_http_tool(self, server_name: str, tool_name: str, arguments: Dict[str, Any]) -> Dict[str, Any]:
        """通过 HTTP 调用工具"""
        client = self.http_clients.get(server_name)
        if not client:
            return {'success': False, 'error': f'HTTP client not connected: {server_name}'}
        return client.call_tool(tool_name, arguments)

    def _list_stdio_tools(self, server_name: str) -> List[Dict[str, Any]]:
        process = self.processes.get(server_name)
        if not process:
            return []
        try:
            if not self._stdio_initialized.get(server_name):
                self._initialize_stdio(self.servers[server_name], process)
            payload = {
                "jsonrpc": "2.0",
                "id": 10,
                "method": "tools/list",
                "params": {},
            }
            process.stdin.write(json.dumps(payload, ensure_ascii=False) + "\n")
            process.stdin.flush()
            response = self._read_stdio_response(process, timeout=30.0)
            if response and "result" in response:
                return response["result"].get("tools", [])
        except Exception:
            logger.debug("list stdio tools failed: %s", traceback.format_exc())
        return []

    def _list_http_tools(self, server_name: str) -> List[Dict[str, Any]]:
        client = self.http_clients.get(server_name)
        if not client:
            return []
        result = client.list_tools()
        if result.get("success"):
            return result.get("tools", [])
        return []

    def _list_sse_tools(self, server_name: str) -> List[Dict[str, Any]]:
        client = self.http_clients.get(server_name)
        if not client:
            return []
        try:
            return client.list_tools().get("tools", [])
        except Exception:
            logger.debug("list sse tools failed: %s", traceback.format_exc())
            return []

    def _call_sse_tool(self, server_name: str, tool_name: str, arguments: Dict[str, Any]) -> Dict[str, Any]:
        client = self.http_clients.get(server_name)
        if not client:
            return {'success': False, 'error': f'SSE client not connected: {server_name}'}
        try:
            return client.call_tool(tool_name, arguments)
        except Exception as exc:
            return {'success': False, 'error': str(exc)}

    def close(self):
        """关闭所有连接"""
        for name, process in list(self.processes.items()):
            try:
                if process.stdin:
                    process.stdin.close()
                process.terminate()
                process.wait(timeout=5)
            except Exception:
                logger.debug("mcp process cleanup failed: %s", traceback.format_exc())
        self.processes.clear()
        self._stdio_initialized.clear()

        for name, client in list(self.http_clients.items()):
            try:
                client.close()
            except Exception:
                logger.debug("mcp http client cleanup failed: %s", traceback.format_exc())
        self.http_clients.clear()
        self.tools.clear()


# 全局 MCP 客户端
mcp_client = MCPClient()
