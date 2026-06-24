"""
PRISM Agent - MCP HTTP/SSE 传输
支持远程 MCP 服务器连接
"""

import json
import time
import threading
from typing import Dict, Any, Optional, List
from dataclasses import dataclass
from pathlib import Path

try:
    import requests
    _REQUESTS_AVAILABLE = True
except Exception:
    _REQUESTS_AVAILABLE = False


class MCPHTTPClient:
    """MCP HTTP/SSE 客户端"""
    
    def __init__(self, base_url: str):
        self.base_url = base_url.rstrip('/')
        self.session = requests.Session() if _REQUESTS_AVAILABLE else None
        self._initialized = False
    
    def _headers(self) -> Dict[str, str]:
        return {
            'Content-Type': 'application/json',
            'Accept': 'application/json, text/event-stream',
        }
    
    def initialize(self) -> Dict[str, Any]:
        if self._initialized:
            return {'success': True}
        
        payload = {
            'jsonrpc': '2.0',
            'id': 1,
            'method': 'initialize',
            'params': {
                'protocolVersion': '2024-11-05',
                'capabilities': {},
                'clientInfo': {'name': 'prism', 'version': '0.1.0'},
            },
        }
        
        try:
            resp = self.session.post(
                f"{self.base_url}/mcp",
                headers=self._headers(),
                json=payload,
                timeout=30,
            )
            data = resp.json()
            self._initialized = 'result' in data
            return {'success': self._initialized, 'result': data.get('result')}
        except Exception as e:
            return {'success': False, 'error': str(e)}
    
    def list_tools(self) -> Dict[str, Any]:
        init = self.initialize()
        if not init.get('success'):
            return init
        
        payload = {
            'jsonrpc': '2.0',
            'id': 2,
            'method': 'tools/list',
            'params': {},
        }
        
        try:
            resp = self.session.post(
                f"{self.base_url}/mcp",
                headers=self._headers(),
                json=payload,
                timeout=30,
            )
            data = resp.json()
            if 'result' in data:
                tools = data['result'].get('tools', [])
                return {'success': True, 'tools': tools}
            return {'success': False, 'error': data.get('error', {}).get('message', 'Unknown error')}
        except Exception as e:
            return {'success': False, 'error': str(e)}
    
    def call_tool(self, name: str, arguments: Dict[str, Any]) -> Dict[str, Any]:
        init = self.initialize()
        if not init.get('success'):
            return init
        
        payload = {
            'jsonrpc': '2.0',
            'id': 3,
            'method': 'tools/call',
            'params': {
                'name': name,
                'arguments': arguments,
            },
        }
        
        try:
            resp = self.session.post(
                f"{self.base_url}/mcp",
                headers=self._headers(),
                json=payload,
                timeout=30,
            )
            data = resp.json()
            if 'result' in data:
                return {'success': True, 'result': data['result']}
            return {'success': False, 'error': data.get('error', {}).get('message', 'Unknown error')}
        except Exception as e:
            return {'success': False, 'error': str(e)}
    
    def close(self):
        if self.session:
            try:
                self.session.close()
            except Exception:
                pass
        self._initialized = False
