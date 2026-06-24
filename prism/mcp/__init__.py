"""
PRISM Agent - MCP (Model Context Protocol) 支持
整合 Hermes 的 MCP 客户端能力
支持 stdio 和 HTTP 两种传输模式
"""

import json
import subprocess
import asyncio
from typing import Dict, Any, Optional, List
from dataclasses import dataclass
from pathlib import Path


@dataclass
class MCPServer:
    """MCP 服务器配置"""
    name: str
    transport: str  # stdio | http | sse
    command: Optional[str] = None  # stdio 模式：启动命令
    url: Optional[str] = None  # http/sse 模式：服务器地址
    args: List[str] = None  # stdio 模式：参数
    enabled: bool = True
    
    def __post_init__(self):
        if self.args is None:
            self.args = []


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
    
    def add_server(self, server: MCPServer):
        """添加 MCP 服务器"""
        self.servers[server.name] = server
        if server.enabled:
            self._connect_server(server)
    
    def _connect_server(self, server: MCPServer):
        """连接到 MCP 服务器"""
        if server.transport == "stdio":
            self._connect_stdio(server)
        elif server.transport in ["http", "sse"]:
            self._connect_http(server)
    
    def _connect_stdio(self, server: MCPServer):
        """通过 stdio 连接"""
        try:
            process = subprocess.Popen(
                [server.command] + server.args,
                stdin=subprocess.PIPE,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                bufsize=1,
            )
            self.processes[server.name] = process
            print(f"[MCP] 已连接 stdio 服务器: {server.name}")
        except Exception as e:
            print(f"[MCP] 连接失败 {server.name}: {e}")
    
    def _connect_http(self, server: MCPServer):
        """通过 HTTP/SSE 连接（简化版）"""
        # HTTP/SSE 模式需要额外的 HTTP 客户端
        # 这里先做占位，后续实现
        print(f"[MCP] HTTP 服务器 {server.name} 待实现: {server.url}")
    
    def list_tools(self, server_name: Optional[str] = None) -> List[Dict[str, Any]]:
        """
        列出可用工具
        
        Args:
            server_name: 指定服务器名，None 表示所有服务器
        """
        tools = []
        servers = [server_name] if server_name else list(self.servers.keys())
        
        for name in servers:
            if name in self.tools:
                tools.extend(self.tools[name])
        
        return tools
    
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
        else:
            return {'success': False, 'error': 'HTTP transport not implemented yet'}
    
    def _call_stdio_tool(self, server: MCPServer, tool_name: str, arguments: Dict[str, Any]) -> Dict[str, Any]:
        """通过 stdio 调用工具"""
        process = self.processes.get(server.name)
        if not process:
            return {'success': False, 'error': f'Server {server.name} not connected'}
        
        try:
            # 构建 MCP 请求
            request = {
                "jsonrpc": "2.0",
                "id": 1,
                "method": "tools/call",
                "params": {
                    "name": tool_name,
                    "arguments": arguments,
                }
            }
            
            # 发送请求
            request_str = json.dumps(request) + "\n"
            process.stdin.write(request_str)
            process.stdin.flush()
            
            # 读取响应
            response_line = process.stdout.readline()
            if not response_line:
                return {'success': False, 'error': 'No response from server'}
            
            response = json.loads(response_line)
            
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
    
    def close(self):
        """关闭所有连接"""
        for name, process in self.processes.items():
            try:
                process.terminate()
                process.wait(timeout=5)
            except Exception:
                pass
        self.processes.clear()


# 全局 MCP 客户端
mcp_client = MCPClient()
