"""
PRISM Agent - MCP SSE 传输
最小 SSE 客户端实现，用于流式 MCP 服务器连接。
"""
from __future__ import annotations

import json
import threading
import time
from typing import Any, Dict, Optional

from prism.logging import logger
import traceback

try:
    import urllib.request
    import urllib.error
    _URLLIB_AVAILABLE = True
except Exception:
    _URLLIB_AVAILABLE = False


class MCPSSEClient:
    """MCP SSE 客户端，支持流式事件"""

    def __init__(self, base_url: str):
        self.base_url = base_url.rstrip('/')
        self._initialized = False

    def initialize(self) -> Dict[str, Any]:
        if self._initialized:
            return {'success': True}
        # SSE 通常走 GET /sse 建立事件流，此处做最小 handshake
        try:
            url = f"{self.base_url}/sse"
            req = urllib.request.Request(url, method='GET')
            with urllib.request.urlopen(req, timeout=10) as resp:
                # 不读取完整流，只验证连接可达
                self._initialized = True
                return {'success': True}
        except Exception as exc:
            logger.debug("sse init failed: %s", traceback.format_exc())
            return {'success': False, 'error': str(exc)}

    def list_tools(self) -> Dict[str, Any]:
        init = self.initialize()
        if not init.get('success'):
            return init
        try:
            payload = {
                'jsonrpc': '2.0',
                'id': 2,
                'method': 'tools/list',
                'params': {},
            }
            req = urllib.request.Request(
                f"{self.base_url}/mcp",
                data=json.dumps(payload, ensure_ascii=False).encode('utf-8'),
                headers={'Content-Type': 'application/json'},
                method='POST',
            )
            with urllib.request.urlopen(req, timeout=30) as resp:
                data = json.loads(resp.read().decode('utf-8'))
            if 'error' in data:
                return {'success': False, 'error': data['error'].get('message', 'Unknown error')}
            tools = data.get('result', {}).get('tools', [])
            return {'success': True, 'tools': tools}
        except Exception as exc:
            return {'success': False, 'error': str(exc)}

    def call_tool(self, name: str, arguments: Dict[str, Any]) -> Dict[str, Any]:
        init = self.initialize()
        if not init.get('success'):
            return init
        try:
            payload = {
                'jsonrpc': '2.0',
                'id': 3,
                'method': 'tools/call',
                'params': {
                    'name': name,
                    'arguments': arguments,
                },
            }
            req = urllib.request.Request(
                f"{self.base_url}/mcp",
                data=json.dumps(payload, ensure_ascii=False).encode('utf-8'),
                headers={'Content-Type': 'application/json'},
                method='POST',
            )
            with urllib.request.urlopen(req, timeout=30) as resp:
                data = json.loads(resp.read().decode('utf-8'))
            if 'error' in data:
                return {'success': False, 'error': data['error'].get('message', 'Unknown error')}
            return {'success': True, 'result': data.get('result')}
        except Exception as exc:
            return {'success': False, 'error': str(exc)}

    def close(self):
        self._initialized = False
