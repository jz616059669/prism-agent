"""
PRISM Agent - MCP (Model Context Protocol) 支持
整合 Hermes 的 MCP 客户端能力
支持 stdio 和 HTTP 两种传输模式
"""

import json
import os
import queue
import subprocess
import threading
import time
from typing import Dict, Any, Optional, List
from dataclasses import dataclass
from pathlib import Path

from prism.logging import logger
import traceback

try:
    from prism import __version__ as _PRISM_VERSION
except Exception:
    _PRISM_VERSION = "2.1.6"

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
    args: List[str] = None  # stdio 模式：命令参数
    env: Optional[Dict[str, str]] = None  # 环境变量
    enabled: bool = True  # 是否启用
    timeout: int = 30  # 默认超时（秒）
    retries: int = 2  # 默认重试次数
    tool_timeouts: Optional[Dict[str, int]] = None  # 工具级超时覆盖

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
        self._stdio_queues: Dict[str, "queue.Queue[Optional[str]]"] = {}
        self._stdio_threads: Dict[str, threading.Thread] = {}
        self._result_cache: Dict[str, Dict[str, Any]] = {}
        self._cache_ttl: int = 60
        self._cache_lock = threading.Lock()
        self._cache_hits: int = 0
        self._cache_misses: int = 0
        self._config_path: Optional[str] = None
        self._config_mtime: float = 0.0
        self._watcher_thread: Optional[threading.Thread] = None
        self._watcher_stop = threading.Event()
        self._circuit_breaker: Dict[str, Dict[str, int]] = {}
        self._circuit_threshold: int = 3

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
            self._stdio_queues.setdefault(server.name, queue.Queue())
            self._stdio_threads.setdefault(server.name, threading.Thread(target=self._stdio_reader, args=(server.name, process), daemon=True))
            self._stdio_threads[server.name].start()
            print(f"[MCP] 已连接 stdio 服务器: {server.name}")
            self._initialize_stdio(server, process)
        except Exception as e:
            print(f"[MCP] 连接失败 {server.name}: {e}")

    def _stdio_reader(self, server_name: str, process: subprocess.Popen) -> None:
        """后台线程持续读取 stdout 行并放入队列"""
        q = self._stdio_queues.get(server_name)
        if q is None:
            return
        try:
            for line in process.stdout:
                q.put(line)
        except Exception:
            logger.debug("stdio reader stopped for %s", server_name, exc_info=True)
        finally:
            q.put(None)

    def _read_stdio_response(self, server_name: str, timeout: float = 5.0) -> Optional[Dict[str, Any]]:
        """从队列读取 stdio JSON，跳过通知，返回首个带 result/error 的响应"""
        q = self._stdio_queues.get(server_name)
        if q is None:
            return None
        deadline = time.time() + timeout
        while time.time() < deadline:
            try:
                item = q.get(timeout=max(deadline - time.time(), 0.01))
            except queue.Empty:
                return None
            if item is None:
                return None
            line = item.strip()
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
                        "clientInfo": {"name": "prism", "version": _PRISM_VERSION},
                    },
                }
                request_str = json.dumps(init_request, ensure_ascii=False) + "\n"
                if process.poll() is not None:
                    raise RuntimeError(f"stdio server {server.name} already exited")
                process.stdin.write(request_str)
                process.stdin.flush()

                response = self._read_stdio_response(server.name, timeout=5.0)
                if response and "result" in response:
                    self._stdio_initialized[server.name] = True
                    notify = {"jsonrpc": "2.0", "method": "notifications/initialized"}
                    if process.poll() is None:
                        process.stdin.write(json.dumps(notify, ensure_ascii=False) + "\n")
                        process.stdin.flush()
                    print(f"[MCP] stdio 服务器初始化成功: {server.name}")
                else:
                    # 宽松处理：部分简易 server 不遵循完整握手
                    self._stdio_initialized[server.name] = True
                    print(f"[MCP] stdio 服务器 {server.name} 未返回有效初始化响应，仍允许调用")
            except Exception as e:
                self._stdio_initialized.pop(server.name, None)
                print(f"[MCP] stdio 初始化失败 {server.name}: {e}")

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

    def list_tools(self, server_name: Optional[str] = None, refresh: bool = False) -> List[Dict[str, Any]]:
        """
        列出可用工具

        Args:
            server_name: 指定服务器名，None 表示所有服务器
            refresh: 强制刷新工具列表
        """
        servers = [server_name] if server_name else list(self.servers.keys())
        tools = []
        for name in servers:
            if refresh:
                self.tools.pop(name, None)
            self._refresh_tools(name)
            tools.extend(self.tools.get(name, []))
        return tools

    def refresh_tools(self, server_name: Optional[str] = None) -> None:
        """强制刷新一个或多个服务器的工具列表"""
        self.list_tools(server_name=server_name, refresh=True)

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

        # 熔断：连续失败达到阈值后短暂跳过
        state = self._circuit_breaker.get(server_name)
        if state and state.get('failures', 0) >= self._circuit_threshold:
            opened_at = state.get('opened_at', 0)
            if time.time() - opened_at < 10:
                return {'success': False, 'error': f'MCP {server_name} circuit open'}
            else:
                self._circuit_breaker.pop(server_name, None)

        cached = self.get_cached(server_name, tool_name, arguments)
        if cached is not None:
            return cached

        timeout = getattr(server, 'timeout', 30) or 30
        if server.tool_timeouts and tool_name in server.tool_timeouts:
            timeout = server.tool_timeouts[tool_name]
        retries = getattr(server, 'retries', 2) or 2
        last_error = None
        for attempt in range(1, max(retries, 1) + 1):
            try:
                if server.transport == "stdio":
                    result = self._call_stdio_tool(server, tool_name, arguments, timeout=timeout)
                elif server.transport == "http":
                    result = self._call_http_tool(server_name, tool_name, arguments, timeout=timeout)
                elif server.transport == "sse":
                    result = self._call_sse_tool(server_name, tool_name, arguments, timeout=timeout)
                else:
                    result = {'success': False, 'error': f'Unsupported transport: {server.transport}'}
                if result.get('success'):
                    self.set_cached(server_name, tool_name, arguments, result)
                    failures = self._circuit_breaker.get(server_name, {}).get('failures', 0)
                    if failures:
                        self._circuit_breaker[server_name] = {'failures': 0, 'opened_at': 0}
                    return result
                last_error = result.get('error')
            except Exception as e:
                last_error = str(e)
                logger.debug("mcp call attempt %s/%s failed: %s", attempt, retries, e, exc_info=True)
        failures = self._circuit_breaker.get(server_name, {}).get('failures', 0) + 1
        if failures >= self._circuit_threshold:
            self._circuit_breaker[server_name] = {'failures': failures, 'opened_at': time.time()}
            logger.warning("mcp circuit breaker open: %s", server_name)
        return {'success': False, 'error': f'MCP call failed after {retries} attempts: {last_error}'}

    def _call_stdio_tool(self, server: MCPServer, tool_name: str, arguments: Dict[str, Any], timeout: float = 30.0) -> Dict[str, Any]:
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
            if process.poll() is not None:
                return {'success': False, 'error': f'Server {server.name} already exited'}
            process.stdin.write(request_str)
            process.stdin.flush()

            response = self._read_stdio_response(server.name, timeout=timeout)
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

    def _call_http_tool(self, server_name: str, tool_name: str, arguments: Dict[str, Any], timeout: int = 30) -> Dict[str, Any]:
        """通过 HTTP 调用工具"""
        client = self.http_clients.get(server_name)
        if not client:
            return {'success': False, 'error': f'HTTP client not connected: {server_name}'}
        return client.call_tool(tool_name, arguments, timeout=timeout)

    def _list_stdio_tools(self, server_name: str) -> List[Dict[str, Any]]:
        process = self.processes.get(server_name)
        if not process:
            return []
        try:
            if not self._stdio_initialized.get(server_name):
                self._initialize_stdio(self.servers[server_name], process)
            timeout = getattr(self.servers.get(server_name), 'timeout', 30) or 30
            payload = {
                "jsonrpc": "2.0",
                "id": 10,
                "method": "tools/list",
                "params": {},
            }
            process.stdin.write(json.dumps(payload, ensure_ascii=False) + "\n")
            process.stdin.flush()
            response = self._read_stdio_response(server_name, timeout=timeout)
            if response and "result" in response:
                return response["result"].get("tools", [])
        except Exception:
            logger.debug("list stdio tools failed: %s", traceback.format_exc())
        return []

    def _list_http_tools(self, server_name: str) -> List[Dict[str, Any]]:
        client = self.http_clients.get(server_name)
        if not client:
            return []
        timeout = getattr(self.servers.get(server_name), 'timeout', 30) or 30
        result = client.list_tools(timeout=timeout)
        if result.get("success"):
            return result.get("tools", [])
        return []

    def _list_sse_tools(self, server_name: str) -> List[Dict[str, Any]]:
        client = self.http_clients.get(server_name)
        if not client:
            return []
        try:
            timeout = getattr(self.servers.get(server_name), 'timeout', 30) or 30
            return client.list_tools(timeout=timeout).get("tools", [])
        except Exception:
            logger.debug("list sse tools failed: %s", traceback.format_exc())
            return []

    def _call_sse_tool(self, server_name: str, tool_name: str, arguments: Dict[str, Any], timeout: int = 30) -> Dict[str, Any]:
        client = self.http_clients.get(server_name)
        if not client:
            return {'success': False, 'error': f'SSE client not connected: {server_name}'}
        try:
            return client.call_tool(tool_name, arguments, timeout=timeout)
        except Exception as exc:
            return {'success': False, 'error': str(exc)}

    def close(self):
        """关闭所有连接"""
        for name, process in list(self.processes.items()):
            try:
                if process.stdin:
                    process.stdin.close()
                process.terminate()
                try:
                    process.wait(timeout=5)
                except subprocess.TimeoutExpired:
                    process.kill()
                    try:
                        process.wait(timeout=5)
                    except subprocess.TimeoutExpired:
                        pass
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

    def get_server_status(self, server_name: Optional[str] = None) -> Dict[str, Any]:
        """获取服务器连接状态"""
        result = {}
        names = [server_name] if server_name else list(self.servers.keys())
        for name in names:
            server = self.servers.get(name)
            if not server:
                continue
            status = {
                "transport": server.transport,
                "enabled": server.enabled,
                "connected": False,
                "tool_count": 0,
            }
            if server.transport == "stdio":
                process = self.processes.get(name)
                status["connected"] = bool(process and process.poll() is None)
                status["initialized"] = bool(self._stdio_initialized.get(name))
                status["tool_count"] = len(self.tools.get(name, []))
            elif server.transport in ("http", "sse"):
                client = self.http_clients.get(name)
                status["connected"] = client is not None
                status["tool_count"] = len(self.tools.get(name, []))
            result[name] = status
        return result

    # -------------------- tool result cache --------------------
    def _cache_key(self, server_name: str, tool_name: str, arguments: Dict[str, Any]) -> str:
        return f"{server_name}::{tool_name}::{json.dumps(arguments, ensure_ascii=False, sort_keys=True)}"

    def get_cached(self, server_name: str, tool_name: str, arguments: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        key = self._cache_key(server_name, tool_name, arguments)
        with self._cache_lock:
            item = self._result_cache.get(key)
            if not item:
                self._cache_misses += 1
                return None
            if time.time() - item["ts"] > self._cache_ttl:
                self._result_cache.pop(key, None)
                self._cache_misses += 1
                return None
            self._cache_hits += 1
            return item["value"]

    def set_cached(self, server_name: str, tool_name: str, arguments: Dict[str, Any], value: Dict[str, Any]) -> None:
        key = self._cache_key(server_name, tool_name, arguments)
        with self._cache_lock:
            self._result_cache[key] = {"ts": time.time(), "value": value}

    def invalidate_cache(self, server_name: Optional[str] = None) -> None:
        with self._cache_lock:
            if server_name is None:
                self._result_cache.clear()
                return
            for key in list(self._result_cache.keys()):
                if key.startswith(f"{server_name}::"):
                    self._result_cache.pop(key, None)

    def get_cache_metrics(self) -> Dict[str, int]:
        """获取缓存命中率统计"""
        with self._cache_lock:
            return {
                "hits": self._cache_hits,
                "misses": self._cache_misses,
                "size": len(self._result_cache),
                "ttl": self._cache_ttl,
            }

    def set_cache_ttl(self, ttl: int) -> None:
        """动态调整缓存 TTL（秒）"""
        if ttl > 0:
            self._cache_ttl = ttl

    # -------------------- config hot reload --------------------
    def watch_config(self, config_path: Optional[str] = None) -> None:
        """后台监听 MCP 配置文件变更，自动热重载"""
        if self._watcher_thread and self._watcher_thread.is_alive():
            return
        if not config_path:
            from prism.paths import PRISM_HOME
            config_path = str(PRISM_HOME / "mcp.json")
        self._config_path = config_path
        try:
            self._config_mtime = Path(config_path).stat().st_mtime
        except Exception:
            self._config_mtime = 0.0
        self._watcher_stop.clear()
        self._watcher_thread = threading.Thread(target=self._config_watcher, daemon=True)
        self._watcher_thread.start()

    def _config_watcher(self) -> None:
        while not self._watcher_stop.is_set():
            try:
                path = Path(self._config_path) if self._config_path else None
                if path and path.exists():
                    mtime = path.stat().st_mtime
                    if mtime != self._config_mtime:
                        self._config_mtime = mtime
                        self._reload_config()
            except Exception:
                logger.debug("mcp config watcher error", exc_info=True)
            self._watcher_stop.wait(2.0)

    def _reload_config(self) -> None:
        try:
            from prism.mcp.config_loader import load_mcp_config, setup_mcp_servers
            new_servers = load_mcp_config(self._config_path)
            new_names = {s.name for s in new_servers if s.enabled}
            existing_names = set(self.servers.keys())
            for name in existing_names - new_names:
                self._remove_server(name)
            added = []
            for server in new_servers:
                if server.name not in self.servers:
                    self.add_server(server)
                    added.append(server.name)
            if added:
                print(f"[MCP] 热重载新增服务器: {added}")
            self.invalidate_cache()
        except Exception as e:
            print(f"[MCP] 热重载失败: {e}")

    def _remove_server(self, name: str) -> None:
        process = self.processes.pop(name, None)
        if process and process.poll() is None:
            try:
                process.terminate()
                try:
                    process.wait(timeout=5)
                except subprocess.TimeoutExpired:
                    process.kill()
            except Exception:
                logger.debug("mcp server remove failed: %s", name, exc_info=True)
        self.http_clients.pop(name, None)
        self.tools.pop(name, None)
        self._stdio_initialized.pop(name, None)
        self._stdio_locks.pop(name, None)
        self._stdio_queues.pop(name, None)
        self._stdio_threads.pop(name, None)
        self.servers.pop(name, None)


# 全局 MCP 客户端
mcp_client = MCPClient()
