"""
PRISM Agent - MCP HTTP/SSE 传输
支持远程 MCP 服务器连接
"""

import json
import time
import threading
import urllib.request
import urllib.error
from typing import Dict, Any, Optional, List
from dataclasses import dataclass
from pathlib import Path


class MCPHTTPClient:
    """MCP HTTP/SSE 客户端"""
    
    def __init__(self, base_url: str):
        self.base_url = base_url.rstrip('/')
        # Use urllib instead of requests to avoid import-time hangs
        self._initialized = False
    
    def _headers(self) -> Dict[str, str]:
        return {
            'Content-Type': 'application/json',
            'Accept': 'application/json, text/event-stream',
        }

    def _request(self, method: str, path: str, payload: dict, timeout: int = 30) -> Dict[str, Any]:
        """Make HTTP request using urllib"""
        url = f"{self.base_url}{path}"
        data = json.dumps(payload, ensure_ascii=False).encode('utf-8')
        req = urllib.request.Request(url, data=data, headers=self._headers(), method=method)
        try:
            with urllib.request.urlopen(req, timeout=timeout) as resp:
                raw = resp.read().decode('utf-8')
                return json.loads(raw)
        except urllib.error.HTTPError as e:
            body = e.read().decode('utf-8', errors='replace')
            try:
                return json.loads(body)
            except Exception:
                return {'error': {'message': str(e), 'body': body[:200]}}
        except Exception as e:
            return {'error': {'message': str(e)}}
    
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
                'clientInfo': {'name': 'prism', 'version': '1.0.1'},
            },
        }
        
        try:
            data = self._request('POST', '/mcp', payload, timeout=30)
            if 'error' in data:
                return {'success': False, 'error': data['error'].get('message', 'Unknown error')}
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
            data = self._request('POST', '/mcp', payload, timeout=30)
            if 'error' in data:
                return {'success': False, 'error': data['error'].get('message', 'Unknown error')}
            if 'result' in data:
                tools = data['result'].get('tools', [])
                return {'success': True, 'tools': tools}
            return {'success': False, 'error': 'Unknown error'}
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
            data = self._request('POST', '/mcp', payload, timeout=30)
            if 'error' in data:
                return {'success': False, 'error': data['error'].get('message', 'Unknown error')}
            if 'result' in data:
                return {'success': True, 'result': data['result']}
            return {'success': False, 'error': 'Unknown error'}
        except Exception as e:
            return {'success': False, 'error': str(e)}
    
    def close(self):
        self._initialized = False
