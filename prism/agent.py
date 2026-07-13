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
except Exception:  # noqa: BLE001
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

        # RAG 本地知识库
        self._rag = None
        self._rag_enabled = False
        self._rag_top_k = 3
        try:
            from prism.config import config as cfg
            rag_cfg = cfg.get('rag', {}) or {}
            if rag_cfg.get('enabled'):
                from prism.rag import LocalRAG
                self._rag = LocalRAG(
                    root=rag_cfg.get('root'),
                    chunk_size=int(rag_cfg.get('chunk_size', 600) or 600),
                    overlap=int(rag_cfg.get('overlap', 120) or 120),
                )
                self._rag_enabled = True
                self._rag_top_k = int(rag_cfg.get('top_k', 3) or 3)
        except (ImportError, Exception):
            pass

        # 初始化系统消息
        self.messages.append(Message(
            role="system",
            content=self.system_prompt,
        ))

    def _trim_messages(self):
        """保留 system + 最新 max_messages 条；超出时对旧消息做摘要压缩。"""
        if len(self.messages) <= self.max_messages:
            return
        # 保留 system 和最后 N 条
        system = self.messages[:1]
        tail = self.messages[-(self.max_messages - 1):]
        old = self.messages[1:len(self.messages) - len(tail)]
        if old and not getattr(self, "_trimming_in_progress", False):
            try:
                self._trimming_in_progress = True
                summary = self._summarize_messages(old)
                if summary:
                    system.append(Message(role="system", content=f"[历史摘要] {summary}"))
            finally:
                self._trimming_in_progress = False
        self.messages = system + tail
        logger.info("messages trimmed: total=%d, kept=%d", len(old) + len(system) + len(tail), len(system) + len(tail))

    def _summarize_messages(self, messages: list) -> Optional[str]:
        """对一批旧消息做简短摘要，返回可读文本；失败时返回 None。"""
        try:
            if not messages:
                return None
            lines: List[str] = []
            for m in messages:
                role = getattr(m, "role", "")
                c = (getattr(m, "content", "") or "").strip().replace("\n", " ")
                if role == "user":
                    lines.append(f"USER: {c[:220]}")
                elif role == "assistant":
                    lines.append(f"ASSISTANT: {c[:220]}")
            if not lines:
                return None
            text = "\n".join(lines)
            if len(text) > 500:
                text = text[:497] + "..."
            return text
        except (TypeError, AttributeError):
            return None

    def decompose_plan(self, user_message: str) -> Optional[str]:
        """
        任务规划：将复杂请求拆成 2-5 个可执行步骤，返回 plan 文本。
        仅在任务明显复杂时启用，避免简单请求过度拆解。
        """
        try:
            text = (user_message or "").strip()
            if len(text) < 20:
                return None
            # 保守触发：只有包含明显的多阶段暗示词才拆解
            hints = ["步骤", "先", "然后", "最后", "整个", "完整", "系列", "批量", "规划", "计划", "analyse", "analyze", "plan", "project", "设计", "开发"]
            if not any(h in text.lower() for h in hints):
                return None
            prompt = (
                "用户请求：\n" + text + "\n\n"
                "请将任务拆成 2-5 个可执行步骤，输出严格 JSON：\n"
                '{"plan": ["步骤1", "步骤2", "步骤3"]}\n'
                "要求：每步具体、可执行、无冗余。"
            )
            from prism.agent import create_agent
            planner = create_agent(enable_auto_memory=False)
            planner.session_id = getattr(self, "session_id", "") or ""
            planner._persist_disabled = True
            planner._session_json_enabled = False
            result = planner.chat(user_message=prompt)
            try:
                planner.close()
            except Exception:
                pass
            data = json.loads(result or "{}")
            plan = data.get("plan") or []
            if not isinstance(plan, list) or len(plan) < 2:
                return None
            lines = ["【任务规划】"] + [f"{i+1}. {step}" for i, step in enumerate(plan[:5])]
            return "\n".join(lines)
        except (TypeError, ValueError, Exception):
            return None

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
- 工具使用：只调用用户请求中明确需要或与当前任务直接相关的工具；若无工具调用必要，不要为了演示而执行工具。
- 当用户要求生成文件、保存文件、安装包、执行脚本时，优先直接生成或完成，减少反复确认。
"""
    
    def _inject_memory_context(self, user_message: str) -> None:
        """动态注入记忆上下文：身份类优先，再按当前query召回相关记忆"""
        try:
            base = (self.system_prompt or "").rstrip()
            # 移除旧记忆块，避免重复堆叠
            if "## 记忆上下文" in base:
                base = base[: base.index("## 记忆上下文")].rstrip()

            identities = [m for m in persistent_memory._index.values() if m.category == "user_profile"]
            identity_block = ""
            if identities:
                lines = ["【身份】"]
                for m in identities[:3]:
                    lines.append(f"- {m.key}: {m.value}")
                identity_block = "\n" + "\n".join(lines)

            # 只根据当前 query 做轻量召回，避免堆满 context
            query_matches = persistent_memory.search(user_message, category=None, limit=3)
            query_block = ""
            seen = set()
            if query_matches:
                lines = ["【相关】"]
                for m in query_matches:
                    if m.key in seen:
                        continue
                    seen.add(m.key)
                    lines.append(f"- [{m.category}] {m.key}: {m.value[:100]}")
                query_block = "\n" + "\n".join(lines)

            # 兜底：按综合重要度补齐到总数不超过 8
            rest = sorted(
                [m for m in persistent_memory._index.values() if m.category != "user_profile" and m.key not in seen],
                key=lambda m: persistent_memory._importance(m),
                reverse=True,
            )[: max(0, 5 - len(query_matches))]
            rest_block = ""
            if rest:
                lines = []
                for m in rest:
                    lines.append(f"- [{m.category}] {m.key}: {m.value[:80]}")
                rest_block = "\n" + "\n".join(lines)

            injection = identity_block + query_block + rest_block
            if injection:
                self.system_prompt = base + "\n## 记忆上下文" + injection
                if self.messages and getattr(self.messages[0], "role", "") == "system":
                    self.messages[0].content = self.system_prompt
        except (TypeError, AttributeError, Exception):
            logger.debug("inject memory context failed: %s", traceback.format_exc())

    def _run_self_validation(self, user_message: str, assistant_content: str, tool_calls: list) -> Optional[str]:
        """
        自我校验：检查回复是否真正回答用户问题、是否有明显错误/矛盾。
        返回修正文本；若无需修正则返回 None。
        """
        try:
            if not getattr(self, "validation_enabled", False):
                return None
            if not assistant_content or assistant_content.startswith("Error:"):
                return None
            context = ""
            recent = [m for m in getattr(self, "messages", []) or []][-8:]
            if recent:
                parts = []
                for m in recent:
                    role = getattr(m, "role", "")
                    c = (getattr(m, "content", "") or "").strip().replace("\n", " ")
                    if role == "user":
                        parts.append(f"USER: {c[:200]}")
                    elif role == "assistant":
                        parts.append(f"ASSISTANT: {c[:200]}")
                if parts:
                    context = "近期对话摘要：\n" + "\n".join(parts[-6:]) + "\n\n"
            prompt = (
                "你是 PRISM 的内部校验器，只做 3 件事：\n"
                "1. 检查助手回复是否真正回答用户问题；\n"
                "2. 检查是否存在与前文明显矛盾；\n"
                "3. 检查是否存在明显事实错误/幻觉。\n\n"
                f"{context}"
                f"用户：{user_message[:500]}\n"
                f"助手：{assistant_content[:1000]}\n\n"
                "若存在上述问题，只输出一段简洁的修正文本，不要解释原因。\n"
                "若没有问题，只输出：__PRISM_VALIDATION_PASS__"
            )
            from prism.agent import create_agent
            validator = create_agent(enable_auto_memory=False)
            validator.session_id = getattr(self, "session_id", "") or ""
            validator._persist_disabled = True
            validator._session_json_enabled = False
            result = validator.chat(user_message=prompt)
            try:
                validator.close()
            except Exception:
                pass
            text = (result or "").strip()
            if text == "__PRISM_VALIDATION_PASS__":
                return None
            return text
        except (TypeError, ValueError, Exception):
            return None

    @staticmethod
    def _run_clarification_check(user_message: str) -> Optional[str]:
        """
        前置澄清：如果用户query过于模糊、缺少关键信息，先追问再执行。
        当前实现为保守策略：只拦截极短/无意义输入，避免误判。
        """
        text = (user_message or "").strip()
        if len(text) < 2:
            return "请再详细说明一下你的需求，我来帮你。"
        return None

    def chat(self, user_message: str, on_stream=None, **kwargs) -> str:
        """
        发送消息并获取回复
        on_stream: 可选回调，逐 token 接收文本
        """
        # 展开用户消息中的 @引用（文件/目录/URL）
        try:
            from prism.context_refs import expand_references
            user_message = expand_references(user_message)
        except (ImportError, Exception):
            pass

        # 动态注入记忆上下文：身份类优先，再按当前query召回相关记忆
        self._inject_memory_context(user_message)

        # RAG：本地知识库片段注入
        try:
            if getattr(self, "_rag_enabled", False) and getattr(self, "_rag", None) is not None:
                hits = self._rag.query(user_message, top_k=int(getattr(self, "_rag_top_k", 3) or 3))
                if hits:
                    rag_lines = ["## 本地知识库检索结果"]
                    for i, h in enumerate(hits, 1):
                        rag_lines.append(f"[{i}] {h.get('path')}")
                        rag_lines.append((h.get('text') or '').strip()[:600])
                        rag_lines.append("")
                    user_message = user_message + "\n\n" + "\n".join(rag_lines)
        except (ImportError, Exception):
            pass

        # Run before_chat hooks
        hook_result = hook_manager.run_hooks("before_chat", {"message": user_message, "agent": self})
        if not hook_result.passed:
            return f"[blocked by hook: {hook_result.hook.name}] {hook_result.error}"

        # 自我校验：前置检查是否已有足够信息回答
        try:
            if getattr(self, "validation_enabled", False):
                clarification = self._run_clarification_check(user_message)
                if clarification:
                    return clarification
        except (TypeError, AttributeError, Exception):
            logger.debug("pre-validation failed: %s", traceback.format_exc())

        # 添加用户消息
        self.messages.append(Message(role="user", content=user_message))
        self._trim_messages()

        # 在关键操作前自动保存快照（用于 /rollback）
        # 每 5 轮对话保存一次，避免频繁 IO
        if len(self.messages) % 5 == 0:
            try:
                from prism.checkpoint import save_checkpoint
                save_checkpoint(self, label="before_chat")
            except Exception:
                pass
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

        # 自我校验：后置检查回复质量
        try:
            if getattr(self, "validation_enabled", False):
                fixed = self._run_self_validation(user_message, assistant_content, tool_calls)
                if fixed is not None:
                    assistant_content = fixed
        except (TypeError, AttributeError, Exception):
            logger.debug("post-validation failed: %s", traceback.format_exc())

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
        if getattr(self, "enable_auto_memory", False):
            try:
                turn_key = f"chat:{datetime.now().isoformat()}"
                turn_value = f"用户: {user_message}\n助手: {assistant_content or '[无回复]'}"
                persistent_memory.remember(turn_key, turn_value, category="chat_history")
                self._extract_user_facts(user_message, assistant_content or "")
            except (OSError, Exception):
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
        except (TypeError, AttributeError, Exception):
            logger.debug("background review schedule failed: %s", traceback.format_exc())

        return assistant_content

    def execute_tool(self, tool_name: str, **kwargs) -> Dict[str, Any]:
        """
        执行工具
        整合了 Codex 的终端执行 + OpenClaw 的浏览器控制 + MCP 外部工具
        """
        # 重复执行风险检查：相同内容 60 秒内不重复执行
        if tool_name in {"execute_tool", "run_terminal", "web_search", "browser"}:
            marker = f"{tool_name}:{json.dumps(kwargs, ensure_ascii=False, sort_keys=True)}"
            last = getattr(self, "_last_executed", {})
            last_time = last.get(marker, 0)
            now = datetime.now().timestamp()
            if now - last_time < 60:
                return {
                    "success": False,
                    "error": f"为避免重复执行，已拦截 {tool_name}（60 秒内相同调用不重跑）",
                    "provider": getattr(self, "name", "local"),
                }
            last[marker] = now
            self._last_executed = last

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
        
        # 本地工具：失败自动重试，最多 2 次
        for attempt in range(2):
            result = registry.execute(tool_name, **kwargs)
            logger.info("execute tool=%s attempt=%d result=%s", tool_name, attempt + 1, result.get('success'))
            if result.get('success'):
                self.tool_calls.append(ToolCall(
                    id=f"call_{len(self.tool_calls)}",
                    name=tool_name,
                    arguments=kwargs,
                    result=result,
                ))
                self._append_tool_message(tool_name, result)
                return result
            # 第二次失败时，尝试降级策略
            if attempt == 0:
                kwargs = self._fallback_tool_args(tool_name, kwargs)
        
        # 最终失败
        result = registry.execute(tool_name, **kwargs)
        self.tool_calls.append(ToolCall(
            id=f"call_{len(self.tool_calls)}",
            name=tool_name,
            arguments=kwargs,
            result=result,
        ))
        self._append_tool_message(tool_name, result)
        return result
    
    @staticmethod
    def _fallback_tool_args(tool_name: str, kwargs: Dict[str, Any]) -> Dict[str, Any]:
        """工具调用失败时的降级参数策略"""
        if tool_name == "terminal":
            # 增加超时
            return {**kwargs, "timeout": min(int(kwargs.get("timeout", 180)) + 120, 600)}
        if tool_name in ("web_search",):
            # 放宽限制
            return {**kwargs, "limit": max(int(kwargs.get("limit", 5)) + 5, 10)}
        return kwargs
    
    def _try_execute_mcp_tool(self, tool_name: str, **kwargs) -> Optional[Dict[str, Any]]:
        """尝试将工具调用路由到 MCP 外部服务器"""
        try:
            if mcp_client is None:
                return None
            for server_name, tools in mcp_client.tools.items():
                for tool in tools:
                    if tool.get('name') == tool_name:
                        return mcp_client.call_tool(server_name, tool_name, kwargs)
        except (TypeError, AttributeError, Exception):
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
        except (TypeError, AttributeError, Exception):
            logger.debug("tool message append failed: %s", traceback.format_exc())
    
    def list_tools(self) -> List[Dict[str, Any]]:
        """列出可用工具，合并本地 registry 与 MCP 外部工具"""
        local_tools = registry.list_tools()
        mcp_tools: List[Dict[str, Any]] = []
        try:
            if mcp_client is not None:
                mcp_tools = mcp_client.list_tools()
        except (TypeError, AttributeError, Exception):
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
        except (TypeError, OSError, Exception):
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
            except (TypeError, OSError, Exception):
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
            except (TypeError, OSError, Exception):
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
    def _extract_user_facts(self, user_message: str, assistant_content: str) -> None:
        """简单规则提取：用户称呼 / 偏好 / 身份等事实。"""
        import re
        text = user_message or ""
        combined = text + chr(10) + assistant_content
        patterns = [
            (r"我叫([^，。]{1,10})", "user_profile", "name"),
            (r"称呼([^，。]{1,10})", "user_profile", "name"),
            (r"叫我([^，。]{1,10})", "user_profile", "name"),
            (r"不要叫([^，。]{1,10})", "user_profile", "disliked_name"),
            (r"我喜欢([^，。]{1,20})", "user_preference", "like"),
            (r"我不喜欢([^，。]{1,20})", "user_preference", "dislike"),
            (r"记住我的([^，。]{1,20})", "user_profile", "fact"),
        ]
        for pattern, category, key in patterns:
            m = re.search(pattern, combined)
            if m:
                value = m.group(1).strip().strip(chr(10) + chr(13) + "，。,.:; ")
                if value and len(value) <= 20:
                    persistent_memory.remember(key, value, category=category, confidence=0.85)
                break

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
    """带 subagent 支持的 Agent 包装器，增加编排与容错。"""

    def __init__(self, agent: Agent) -> None:
        self.agent = agent
        self.subagents = SubagentManager(agent)

    def delegate(self, subagent_name: str, task: str, max_retries: int = 2) -> str:
        """委托任务给子 Agent，失败自动重试并降级回父级执行。"""
        child = self.subagents.spawn(subagent_name)
        last_result = ""
        for attempt in range(max(1, max_retries)):
            try:
                last_result = child.chat(task)
                if isinstance(last_result, str) and last_result.strip().lower().startswith("error"):
                    if attempt < max_retries - 1:
                        continue
                break
            except (TypeError, AttributeError, Exception):
                if attempt < max_retries - 1:
                    continue
                last_result = "[delegate failed]"
                break
        summary = self.subagents.summarize_back(subagent_name)
        self.agent.messages.append(Message(
            role="tool",
            content=f"[subagent:{subagent_name}] {summary}",
        ))
        return last_result or summary


# 在 Agent 类中添加 subagent 支持
Agent.subagent_manager = property(lambda self: SubagentManager(self))

def create_agent(system_prompt: Optional[str] = None, enable_auto_memory: bool = False) -> Agent:
    """创建 Agent 实例，并同步更新提供商池默认模型"""
    agent = Agent(system_prompt=system_prompt, enable_auto_memory=enable_auto_memory)
    try:
        from prism.config import get_config
        from prism.providers.manager import provider_pool
        provider_pool.set_default_model(get_config().get('model.default', 'step-3.7-flash'))
    except (ImportError, Exception):
        pass
    return agent
