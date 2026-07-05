"""
PRISM Agent - MCP Server
让 PRISM 可以作为 MCP Server 被其他客户端调用，提供工具能力。
"""

from __future__ import annotations

import json
import logging
from typing import Any, Dict, List, Optional

from prism.mcp.protocol import (
    MCP_PROTOCOL_VERSION,
    make_notification,
    make_request,
    make_response,
)

logger = logging.getLogger("prism.mcp_server")


class PrismMCPServer:
    """PRISM 作为 MCP Server，提供标准 MCP 协议接口"""

    def __init__(self) -> None:
        self._tools = self._register_tools()

    def _register_tools(self) -> Dict[str, Dict[str, Any]]:
        """注册可用的 MCP 工具"""
        tools: Dict[str, Dict[str, Any]] = {
            "prism_chat": {
                "name": "prism_chat",
                "description": "与 PRISM Agent 对话，获取 AI 回复",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "message": {"type": "string", "description": "用户消息"},
                        "model": {"type": "string", "description": "模型名称（可选）"},
                    },
                    "required": ["message"],
                },
            },
            "prism_search": {
                "name": "prism_search",
                "description": "搜索网页",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "query": {"type": "string", "description": "搜索关键词"},
                    },
                    "required": ["query"],
                },
            },
            "prism_execute": {
                "name": "prism_execute",
                "description": "执行 Python 代码",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "code": {"type": "string", "description": "Python 代码"},
                    },
                    "required": ["code"],
                },
            },
            "prism_save_session": {
                "name": "prism_save_session",
                "description": "保存当前会话",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "name": {"type": "string", "description": "会话名称"},
                        "tags": {"type": "array", "items": {"type": "string"}, "description": "标签（可选）"},
                    },
                    "required": ["name"],
                },
            },
            "prism_list_sessions": {
                "name": "prism_list_sessions",
                "description": "列出已保存的会话",
                "inputSchema": {"type": "object", "properties": {}},
            },
            "prism_search_sessions": {
                "name": "prism_search_sessions",
                "description": "搜索会话内容",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "query": {"type": "string", "description": "搜索关键词"},
                    },
                    "required": ["query"],
                },
            },
            "prism_remember": {
                "name": "prism_remember",
                "description": "存储记忆",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "key": {"type": "string", "description": "记忆键"},
                        "value": {"type": "string", "description": "记忆值"},
                        "category": {"type": "string", "description": "分类（可选）"},
                    },
                    "required": ["key", "value"],
                },
            },
            "prism_recall": {
                "name": "prism_recall",
                "description": "回忆记忆",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "key": {"type": "string", "description": "记忆键"},
                    },
                    "required": ["key"],
                },
            },
        }

        # Auto-discover tools from registry and expose as MCP tools
        try:
            from prism.tools.registry import registry
            for t in registry.list_tools():
                name = t.get("name") if isinstance(t, dict) else getattr(t, "name", None)
                description = t.get("description") if isinstance(t, dict) else getattr(t, "description", "")
                if name and name not in tools:
                    input_schema = t.get("inputSchema") if isinstance(t, dict) else None
                    tools[name] = {
                        "name": name,
                        "description": description or f"PRISM tool: {name}",
                        "inputSchema": input_schema or {"type": "object", "properties": {}},
                    }
        except Exception as exc:
            logger.debug("mcp tool discovery failed: %s", exc)

        return tools

    def initialize(self) -> Dict[str, Any]:
        """返回 MCP 初始化响应"""
        return {
            "protocolVersion": MCP_PROTOCOL_VERSION,
            "capabilities": {"tools": {}},
            "serverInfo": {"name": "prism", "version": "2.1.2"},
        }

    def handle_request(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        """处理 JSON-RPC 请求"""
        req_id = payload.get("id")
        method = payload.get("method")
        params = payload.get("params", {})

        if method == "initialize":
            result = self.initialize()
            return make_response(req_id, result=result)
        elif method == "initialized":
            return make_response(req_id, result={})
        elif method == "tools/list":
            return make_response(req_id, result={"tools": self.list_tools()})
        elif method == "tools/call":
            name = params.get("name")
            arguments = params.get("arguments", {})
            result = self.call_tool(name, arguments)
            return make_response(req_id, result=result)
        else:
            return make_response(req_id, error={"code": -32601, "message": f"Method not found: {method}"})

    def list_tools(self) -> List[Dict[str, Any]]:
        """列出所有可用工具"""
        return list(self._tools.values())

    def call_tool(self, name: str, arguments: Dict[str, Any]) -> Dict[str, Any]:
        """调用工具"""
        if name not in self._tools:
            return {"error": f"Unknown tool: {name}"}

        try:
            if name == "prism_chat":
                return self._tool_chat(arguments)
            elif name == "prism_search":
                return self._tool_search(arguments)
            elif name == "prism_execute":
                return self._tool_execute(arguments)
            elif name == "prism_save_session":
                return self._tool_save_session(arguments)
            elif name == "prism_list_sessions":
                return self._tool_list_sessions(arguments)
            elif name == "prism_search_sessions":
                return self._tool_search_sessions(arguments)
            elif name == "prism_remember":
                return self._tool_remember(arguments)
            elif name == "prism_recall":
                return self._tool_recall(arguments)
            else:
                # Dynamic dispatch for auto-discovered tools from registry
                return self._tool_dispatch(name, arguments)
        except Exception as exc:
            logger.error("tool %s failed: %s", name, exc)
            return {"error": str(exc)}

    def _tool_chat(self, args: Dict[str, Any]) -> Dict[str, Any]:
        from prism.agent import create_agent
        agent = create_agent()
        message = args.get("message", "")
        if not message:
            return {"error": "message is required"}
        
        # Note: provider_pool does not support changing default model at runtime.
        # If a model override is needed, it should be configured via config or provider selection.
        response = agent.chat(message)
        return {"content": response, "role": "assistant"}

    def _tool_search(self, args: Dict[str, Any]) -> Dict[str, Any]:
        from prism.tools.registry import registry
        result = registry.execute("web_search", query=args.get("query", ""))
        return result if isinstance(result, dict) else {"content": str(result)}

    def _tool_execute(self, args: Dict[str, Any]) -> Dict[str, Any]:
        from prism.tools.registry import registry
        result = registry.execute("code_execution", code=args.get("code", ""))
        return result if isinstance(result, dict) else {"content": str(result)}

    def _tool_save_session(self, args: Dict[str, Any]) -> Dict[str, Any]:
        from prism.agent import create_agent
        agent = create_agent()
        name = args.get("name", "")
        tags = args.get("tags", [])
        if not name:
            return {"error": "name is required"}
        path = agent.save_session(name, tags=tags)
        return {"content": f"Session saved: {path}"}

    def _tool_list_sessions(self, args: Dict[str, Any]) -> Dict[str, Any]:
        from prism.agent import Agent
        sessions = Agent.list_sessions()
        return {"content": sessions}

    def _tool_search_sessions(self, args: Dict[str, Any]) -> Dict[str, Any]:
        from prism.agent import Agent
        query = args.get("query", "")
        results = Agent.search_sessions(query)
        return {"content": results}

    def _tool_remember(self, args: Dict[str, Any]) -> Dict[str, Any]:
        from prism.memory import memory as persistent_memory
        key = args.get("key", "")
        value = args.get("value", "")
        category = args.get("category", "general")
        if not key or not value:
            return {"error": "key and value are required"}
        persistent_memory.remember(key, value, category)
        return {"content": f"Memory stored: {key}"}

    def _tool_recall(self, args: Dict[str, Any]) -> Dict[str, Any]:
        from prism.memory import memory as persistent_memory
        key = args.get("key", "")
        if not key:
            return {"error": "key is required"}
        value = persistent_memory.recall(key)
        return {"content": value or f"No memory found for: {key}"}

    def _tool_dispatch(self, name: str, arguments: Dict[str, Any]) -> Dict[str, Any]:
        """动态分发到 registry 工具，供 MCP 自动发现工具使用"""
        from prism.tools.registry import registry
        result = registry.execute(name, **arguments)
        if isinstance(result, dict):
            return result
        return {"content": str(result)}

    def handle_notification(self, method: str, params: Dict[str, Any]) -> None:
        """处理 JSON-RPC 通知，无返回值"""
        # 当前未实现通知副作用，保持静默
        logger.debug("mcp notification ignored: %s", method)


# 全局 MCP Server 实例
mcp_server = PrismMCPServer()
