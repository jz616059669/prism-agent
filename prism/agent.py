"""
PRISM Agent - 核心Agent循环
整合 Hermes 的上下文压缩 + Codex 的工具调用 + OpenClaw 的浏览器控制
"""

import json
import os
import logging
from pathlib import Path
from typing import List, Dict, Any, Optional, Callable
from dataclasses import dataclass, field
from datetime import datetime

from prism.providers.manager import provider_pool
from prism.tools.registry import registry

logger = logging.getLogger("prism.agent")


@dataclass
class Message:
    """消息结构"""
    role: str  # system | user | assistant | tool
    content: str
    timestamp: datetime = field(default_factory=datetime.now)
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class ToolCall:
    """工具调用"""
    id: str
    name: str
    arguments: Dict[str, Any]
    result: Optional[Dict[str, Any]] = None


class Agent:
    """
    PRISM Agent 核心
    整合：
    - Hermes 的 Skills 系统
    - Codex 的代码执行能力
    - OpenClaw 的浏览器自动化
    - 统一的模型调用接口
    """
    
    def __init__(self, system_prompt: Optional[str] = None):
        self.messages: List[Message] = []
        self.tool_calls: List[ToolCall] = []
        self.system_prompt = system_prompt or self._default_system_prompt()
        self.max_turns = 150
        self.tools_enabled = True
        
        # 初始化系统消息
        self.messages.append(Message(
            role="system",
            content=self.system_prompt,
        ))
    
    def _default_system_prompt(self) -> str:
        """默认系统提示词"""
        return """你是 PRISM Agent，一个强大的 AI 助手。

你可以：
1. 读写文件、执行命令
2. 搜索网页、控制浏览器
3. 执行 Python 代码
4. 管理定时任务
5. 发送消息到 Telegram/Discord/飞书

原则：
- 先理解用户需求，再执行
- 复杂任务拆成步骤
- 遇到问题主动报告，不要隐瞒
- 安全第一，危险操作先确认
"""
    
    def chat(self, user_message: str, on_stream=None) -> str:
        """
        发送消息并获取回复
        on_stream: 可选回调，逐 token 接收文本
        """
        # 添加用户消息
        self.messages.append(Message(role="user", content=user_message))

        # 构建 API 消息格式
        api_messages = [
            {"role": m.role, "content": m.content}
            for m in self.messages
        ]

        # 如果有流式回调，使用流式请求
        if on_stream is not None:
            result = provider_pool.stream_chat(api_messages, on_chunk=on_stream)
        else:
            result = provider_pool.chat(api_messages)

        if not result.get('success'):
            logger.warning("chat failed: %s", result.get('error'))
            return f"Error: {result.get('error', 'Unknown error')}"

        assistant_content = result.get('content', '') or ''
        tool_calls = result.get('tool_calls') or []
        function_call = result.get('function_call')

        if not assistant_content and function_call:
            assistant_content = "[function call] " + str(function_call.get('name', ''))

        if tool_calls:
            assistant_content = (assistant_content + ' ' if assistant_content else '') + "[tool call] " + ", ".join(
                t.get('name', '') for t in tool_calls
            )

        logger.info("chat success model=%s tool_calls=%s", result.get('model'), len(tool_calls))

        # 添加助手回复
        self.messages.append(Message(role="assistant", content=assistant_content))

        return assistant_content

    def execute_tool(self, tool_name: str, **kwargs) -> Dict[str, Any]:
        """
        执行工具
        整合了 Codex 的终端执行 + OpenClaw 的浏览器控制
        """
        if not self.tools_enabled:
            return {'success': False, 'error': 'Tools disabled'}
        
        logger.info("execute tool=%s args=%s", tool_name, kwargs)
        result = registry.execute(tool_name, **kwargs)
        logger.info("execute tool=%s result=%s", tool_name, result.get('success'))
        
        # 记录工具调用
        self.tool_calls.append(ToolCall(
            id=f"call_{len(self.tool_calls)}",
            name=tool_name,
            arguments=kwargs,
            result=result,
        ))
        
        # 浏览器事件回传给消息流
        if tool_name in {"browser_navigate", "browser_snapshot", "browser_disconnect"}:
            try:
                content = ""
                if result.get("success"):
                    if tool_name == "browser_navigate":
                        content = f"[browser] opened: {result.get('url')} | title={result.get('title')}"
                    elif tool_name == "browser_snapshot":
                        content = f"[browser] snapshot: {result.get('title')} | len={len(result.get('content') or '')}"
                    else:
                        content = "[browser] closed"
                else:
                    content = f"[browser] error: {result.get('error')}"
                self.messages.append(Message(role="tool", content=content))
            except Exception:
                pass
        
        return result
    
    def list_tools(self) -> List[Dict[str, str]]:
        """列出可用工具"""
        return registry.list_tools()
    
    def clear_history(self):
        """清空对话历史"""
        self.messages = [self.messages[0]]  # 保留系统消息
        self.tool_calls = []

    def save_session(self, name: str) -> str:
        """保存当前会话到本地"""
        session_dir = Path.home() / ".prism" / "sessions"
        session_dir.mkdir(parents=True, exist_ok=True)
        path = session_dir / f"{name}.json"
        payload = {
            "system_prompt": self.system_prompt,
            "messages": [
                {
                    "role": m.role,
                    "content": m.content,
                    "timestamp": m.timestamp.isoformat() if hasattr(m.timestamp, "isoformat") else str(m.timestamp),
                }
                for m in self.messages
            ],
        }
        path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
        return str(path)

    def load_session(self, name: str) -> bool:
        """从本地加载会话"""
        path = Path.home() / ".prism" / "sessions" / f"{name}.json"
        if not path.exists():
            return False
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
            self.system_prompt = payload.get("system_prompt", self.system_prompt)
            self.messages = []
            for m in payload.get("messages", []):
                ts_raw = m.get("timestamp")
                ts = datetime.fromisoformat(ts_raw) if ts_raw else datetime.now()
                self.messages.append(Message(
                    role=m.get("role", "user"),
                    content=m.get("content", ""),
                    timestamp=ts,
                ))
            return True
        except Exception:
            return False

    @staticmethod
    def list_sessions() -> List[str]:
        """列出已保存的会话"""
        session_dir = Path.home() / ".prism" / "sessions"
        if not session_dir.exists():
            return []
        return [p.stem for p in session_dir.glob("*.json")]

    def delete_session(self, name: str) -> bool:
        """删除已保存的会话"""
        path = Path.home() / ".prism" / "sessions" / f"{name}.json"
        if path.exists():
            path.unlink()
            return True
        return False


def create_agent(system_prompt: Optional[str] = None) -> Agent:
    """创建 Agent 实例"""
    return Agent(system_prompt=system_prompt)
