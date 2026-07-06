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

from prism.logging import logger
import traceback

from prism.providers.manager import provider_pool
from prism.tools.registry import registry
from prism.hooks import hook_manager
from prism.memory import persistent_memory

try:
    from prism.mcp import mcp_client
except Exception:
    mcp_client = None  # type: ignore[assignment]


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
    
    def __init__(self, system_prompt: Optional[str] = None, enable_auto_memory: bool = False):
        self.messages: List[Message] = []
        self.tool_calls: List[ToolCall] = []
        self.system_prompt = system_prompt or self._default_system_prompt()
        self.max_turns = 150
        self.max_messages = 200  # 防止上下文无限增长
        self.tools_enabled = True
        self.enable_auto_memory = enable_auto_memory
        self.review_enabled = bool(int(os.getenv("PRISM_REVIEW_ENABLED", "0") or 0))
        self.review_interval = int(os.getenv("PRISM_REVIEW_INTERVAL", "5") or 5)
        self._review_turn_count = 0
        self.background_review_callback: Optional[Callable[[str], None]] = None
        self._memory_context = persistent_memory.get_context(max_items=5)
        if self._memory_context:
            self.system_prompt = self.system_prompt.rstrip() + "\n\n" + self._memory_context
        
        # 初始化系统消息
        self.messages.append(Message(
            role="system",
            content=self.system_prompt,
        ))

    def _trim_messages(self):
        """保留 system + 最新 max_messages 条，超出时丢弃最早的 user/assistant 对"""
        if len(self.messages) <= self.max_messages:
            return
        # 保留 system 和最后 N 条
        system = self.messages[:1]
        tail = self.messages[-(self.max_messages - 1):]
        self.messages = system + tail
        logger.info("messages trimmed: total=%d, kept=%d", len(self.messages), len(system) + len(tail))
    
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
    
    def chat(self, user_message: str, on_stream=None, **kwargs) -> str:
        """
        发送消息并获取回复
        on_stream: 可选回调，逐 token 接收文本
        """
        # 动态注入记忆上下文，避免仅初始化一次
        try:
            ctx = persistent_memory.get_context(max_items=5)
            if ctx:
                base = (self.system_prompt or "").rstrip()
                injection = "\n\n" + ctx
                if not base.endswith(injection):
                    self.system_prompt = base + injection
                    # 同步第一条 system message
                    if self.messages and getattr(self.messages[0], "role", "") == "system":
                        self.messages[0].content = self.system_prompt
        except Exception:
            logger.debug("inject memory context failed: %s", traceback.format_exc())

        # Run before_chat hooks
        hook_result = hook_manager.run_hooks("before_chat", {"message": user_message, "agent": self})
        if not hook_result.passed:
            return f"[blocked by hook: {hook_result.hook.name}] {hook_result.error}"

        # 添加用户消息
        self.messages.append(Message(role="user", content=user_message))
        self._trim_messages()

        # 构建 API 消息格式
        api_messages = [
            {"role": m.role, "content": m.content}
            for m in self.messages
        ]

        # 如果有流式回调，使用流式请求
        if on_stream is not None:
            result = provider_pool.stream_chat(api_messages, on_chunk=on_stream, **kwargs)
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
        self._trim_messages()

        # Run after_chat hooks
        hook_manager.run_hooks("after_chat", {
            "message": user_message,
            "response": assistant_content,
            "agent": self,
        })

        # 自动记忆：若开启，则将本轮关键信息写入持久记忆
        if getattr(self, "enable_auto_memory", False) and assistant_content:
            try:
                persistent_memory.remember(
                    key=f"chat:{datetime.now().isoformat()}",
                    value=f"用户: {user_message}\n助手: {assistant_content}",
                    category="chat_history",
                )
            except Exception:
                logger.debug("auto memory save failed: %s", traceback.format_exc())

        # Background self-improvement review
        try:
            if getattr(self, "review_enabled", False):
                self._review_turn_count = getattr(self, "_review_turn_count", 0) + 1
                if self._review_turn_count % max(1, getattr(self, "review_interval", 5)) == 0:
                    from prism.self_review import spawn_background_review
                    snapshot = [
                        {"role": m.role, "content": m.content or ""}
                        for m in getattr(self, "messages", []) or []
                    ]
                    spawn_background_review(
                        self,
                        snapshot,
                        review_memory=getattr(self, "enable_auto_memory", False),
                        review_skills=True,
                    )
        except Exception:
            logger.debug("background review schedule failed: %s", traceback.format_exc())

        return assistant_content

    def execute_tool(self, tool_name: str, **kwargs) -> Dict[str, Any]:
        """
        执行工具
        整合了 Codex 的终端执行 + OpenClaw 的浏览器控制 + MCP 外部工具
        """
        if not self.tools_enabled:
            return {'success': False, 'error': 'Tools disabled'}
        
        logger.info("execute tool=%s args=%s", tool_name, kwargs)
        
        # MCP 外部工具路由
        mcp_result = self._try_execute_mcp_tool(tool_name, **kwargs)
        if mcp_result is not None:
            logger.info("execute mcp tool=%s result=%s", tool_name, mcp_result.get('success'))
            self.tool_calls.append(ToolCall(
                id=f"call_{len(self.tool_calls)}",
                name=tool_name,
                arguments=kwargs,
                result=mcp_result,
            ))
            self._append_tool_message(tool_name, mcp_result)
            return mcp_result
        
        # 本地工具
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
        self._append_tool_message(tool_name, result)
        
        return result
    
    def _try_execute_mcp_tool(self, tool_name: str, **kwargs) -> Optional[Dict[str, Any]]:
        """尝试将工具调用路由到 MCP 外部服务器"""
        try:
            if mcp_client is None:
                return None
            for server_name, tools in mcp_client.tools.items():
                for tool in tools:
                    if tool.get('name') == tool_name:
                        return mcp_client.call_tool(server_name, tool_name, kwargs)
        except Exception:
            logger.debug("mcp tool route failed: %s", traceback.format_exc())
        return None
    
    def _append_tool_message(self, tool_name: str, result: Dict[str, Any]) -> None:
        """将工具调用结果写入消息流，保证会话保存/回溯有完整上下文。"""
        try:
            if tool_name.startswith("browser_"):
                content = ""
                if result.get("success"):
                    if tool_name == "browser_navigate":
                        content = f"[browser] opened: {result.get('url')} | title={result.get('title')}"
                    elif tool_name == "browser_snapshot":
                        content = f"[browser] snapshot: {result.get('title')} | len={len(result.get('content') or '')}"
                    elif tool_name == "browser_disconnect":
                        content = "[browser] closed"
                    else:
                        content = f"[browser] {tool_name}: success"
                else:
                    content = f"[browser] error: {result.get('error')}"
            elif tool_name == "terminal":
                content = f"[terminal] exit={result.get('exit_code')} len={len(result.get('output') or '')}"
                if not result.get('success') and result.get('error'):
                    content += f" error={result.get('error')[:100]}"
            elif tool_name == "file_read":
                content = f"[file_read] path={result.get('path')} lines={result.get('total_lines')}"
            elif tool_name == "file_write":
                content = f"[file_write] path={result.get('path')}"
            elif tool_name == "file_patch":
                content = f"[file_patch] path={result.get('path')} success={result.get('success')}"
            else:
                content = f"[{tool_name}] success={result.get('success')}"
                if not result.get('success') and result.get('error'):
                    content += f" error={str(result.get('error'))[:120]}"
            self.messages.append(Message(role="tool", content=content))
        except Exception:
            logger.debug("tool message append failed: %s", traceback.format_exc())
    
    def list_tools(self) -> List[Dict[str, Any]]:
        """列出可用工具，合并本地 registry 与 MCP 外部工具"""
        local_tools = registry.list_tools()
        mcp_tools: List[Dict[str, Any]] = []
        try:
            if mcp_client is not None:
                mcp_tools = mcp_client.list_tools()
        except Exception:
            logger.debug("list mcp tools failed: %s", traceback.format_exc())
        seen = {t.get('name') for t in local_tools}
        merged = list(local_tools)
        for t in mcp_tools:
            if t.get('name') not in seen:
                merged.append({**t, 'source': 'mcp'})
                seen.add(t.get('name'))
        return merged
    
    def clear_history(self):
        """清空对话历史"""
        self.messages = [self.messages[0]]  # 保留系统消息
        self.tool_calls = []

    def save_session(self, name: str, tags: Optional[List[str]] = None) -> str:
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
                    "metadata": m.metadata or {},
                }
                for m in self.messages
            ],
            "tags": tags or [],
            "created_at": datetime.now().isoformat(),
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
                    metadata=m.get("metadata") or {},
                ))
            return True
        except Exception:
            logger.debug("load session failed: %s", traceback.format_exc())
            return False

    def search_sessions(self, query: str) -> List[Dict[str, Any]]:
        """搜索会话内容，返回匹配的会话列表"""
        session_dir = Path.home() / ".prism" / "sessions"
        if not session_dir.exists():
            return []
        
        results = []
        query_lower = query.lower()
        
        for path in session_dir.glob("*.json"):
            try:
                payload = json.loads(path.read_text(encoding="utf-8"))
                messages = payload.get("messages", [])
                
                # 搜索消息内容
                for msg in messages:
                    if query_lower in msg.get("content", "").lower():
                        results.append({
                            "file": path.stem,
                            "role": msg.get("role"),
                            "content": msg.get("content", "")[:200],
                            "timestamp": msg.get("timestamp"),
                        })
                        break  # 每个会话只返回第一个匹配
                
                # 搜索标签
                tags = payload.get("tags", [])
                if any(query_lower in tag.lower() for tag in tags):
                    results.append({
                        "file": path.stem,
                        "role": "tag",
                        "content": f"Tags: {', '.join(tags)}",
                        "timestamp": payload.get("created_at"),
                    })
            except Exception:
                logger.debug("search session failed: %s", traceback.format_exc())
                continue
        
        return results[:50]  # 最多返回50条

    @staticmethod
    def list_sessions() -> List[Dict[str, Any]]:
        """列出已保存的会话"""
        session_dir = Path.home() / ".prism" / "sessions"
        if not session_dir.exists():
            return []
        sessions = []
        for path in session_dir.glob("*.json"):
            try:
                payload = json.loads(path.read_text(encoding="utf-8"))
                sessions.append({
                    "name": path.stem,
                    "tags": payload.get("tags", []),
                    "created_at": payload.get("created_at"),
                    "message_count": len(payload.get("messages", [])),
                })
            except Exception:
                logger.debug("search session failed: %s", traceback.format_exc())
                continue
        return sessions

    def delete_session(self, name: str) -> bool:
        """删除已保存的会话"""
        path = Path.home() / ".prism" / "sessions" / f"{name}.json"
        if path.exists():
            path.unlink()
            return True
        return False




    # ========== 记忆系统 ==========
    def remember(self, key: str, value: str, category: str = "general") -> None:
        """存储到持久记忆"""
        persistent_memory.remember(key, value, category)

    def recall(self, key: str) -> Optional[str]:
        """从持久记忆回忆"""
        return persistent_memory.recall(key)

    def search_memory(self, query: str, limit: int = 5) -> List[str]:
        """搜索持久记忆"""
        results = persistent_memory.search(query, limit=limit)
        return [m.value for m in results]

class SubagentManager:
    """管理子 Agent，借鉴 Codex CLI 的 subagent 分层机制。"""

    def __init__(self, parent_agent: Agent) -> None:
        self.parent = parent_agent
        self._subagents: Dict[str, Agent] = {}

    def spawn(self, name: str, system_prompt: Optional[str] = None) -> Agent:
        """生成一个子 Agent，继承父级上下文摘要。"""
        if name in self._subagents:
            raise ValueError(f"Subagent '{name}' already exists")
        child = Agent(system_prompt=system_prompt)
        self._subagents[name] = child
        logger.info("subagent spawned: %s", name)
        return child

    def get(self, name: str) -> Agent:
        """获取子 Agent。"""
        if name not in self._subagents:
            raise ValueError(f"Subagent '{name}' not found")
        return self._subagents[name]

    def list_subagents(self) -> List[str]:
        """列出所有子 Agent。"""
        return list(self._subagents.keys())

    def destroy(self, name: str) -> None:
        """销毁子 Agent。"""
        if name in self._subagents:
            del self._subagents[name]
            logger.info("subagent destroyed: %s", name)

    def summarize_back(self, name: str) -> str:
        """将子 Agent 的上下文摘要回传给父级。"""
        if name not in self._subagents:
            return ""
        child = self._subagents[name]
        msgs = [m.content for m in child.messages if m.role in {"user", "assistant"}]
        return "\n".join(msgs[-10:])  # 最近10条


class AgentWithSubagents:
    """带 subagent 支持的 Agent 包装器。"""

    def __init__(self, agent: Agent) -> None:
        self.agent = agent
        self.subagents = SubagentManager(agent)

    def delegate(self, subagent_name: str, task: str) -> str:
        """委托任务给子 Agent。"""
        child = self.subagents.spawn(subagent_name)
        result = child.chat(task)
        summary = self.subagents.summarize_back(subagent_name)
        self.agent.messages.append(Message(
            role="tool",
            content=f"[subagent:{subagent_name}] {summary}",
        ))
        return result


# 在 Agent 类中添加 subagent 支持
Agent.subagent_manager = property(lambda self: SubagentManager(self))

def create_agent(system_prompt: Optional[str] = None, enable_auto_memory: bool = False) -> Agent:
    """创建 Agent 实例"""
    return Agent(system_prompt=system_prompt, enable_auto_memory=enable_auto_memory)
