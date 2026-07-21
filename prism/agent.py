"""
PRISM Agent - 核心Agent循环
整合 Hermes 的上下文压缩 + Codex 的工具调用 + OpenClaw 的浏览器控制
"""

import json
import os
import logging
import threading
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
    from prism.task_feedback import record_failure, apply_strategies
except Exception:  # noqa: BLE001
    record_failure = None  # type: ignore[assignment,misc]
    apply_strategies = None  # type: ignore[assignment,misc]

try:
    from prism.mcp import mcp_client
except Exception:  # noqa: BLE001
    mcp_client = None  # type: ignore[assignment]


@dataclass
class Message:
    """消息结构"""
    role: str  # system | user | assistant | tool
    content: str | List[Dict[str, Any]]
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
        self.memory_scope: str = "default"
        self.review_enabled = bool(int(os.getenv("PRISM_REVIEW_ENABLED", "0") or 0))
        self.review_interval = int(os.getenv("PRISM_REVIEW_INTERVAL", "5") or 5)
        self._review_turn_count = 0
        self.background_review_callback: Optional[Callable[[str], None]] = None
        self.session_dir = Path.home() / ".prism" / "sessions"
        self._last_executed: Dict[str, float] = {}
        self._tool_lock = threading.Lock()
        self._memory_context = persistent_memory.get_context(max_items=8, category=self.memory_scope)
        if self._memory_context:
            self.system_prompt = self.system_prompt.rstrip() + "\n\n" + self._memory_context

        # 自动启用记忆语义检索（若配置存在）
        try:
            from prism.config import config as cfg
            emb_cfg = cfg.get('embeddings') or {}
            base_url = emb_cfg.get('base_url') or ''
            api_key = emb_cfg.get('api_key') or ''
            model = emb_cfg.get('model') or ''
            if base_url and api_key and model:
                persistent_memory.configure_embeddings(base_url=base_url, api_key=api_key, model=model)
        except (ImportError, Exception):
            pass

        # 自动化记忆管理（类 Hermes）
        try:
            from prism.memory_manager import memory_manager
            self._memory_manager = memory_manager
            self._memory_manager.memory = persistent_memory
        except Exception:
            self._memory_manager = None

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
        try:
            from prism.retry_strategy import retry_strategy
            retry_strategy.start()
        except Exception:
            pass

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

    def _maybe_plan_and_execute(self, user_message: str) -> Optional[str]:
        """
        复杂任务自动规划执行：
        1. 判断是否复杂
        2. 用 Planner 拆分子任务
        3. 逐个执行并汇总结果
        """
        try:
            if getattr(self, "_planning_in_progress", False):
                return None
            self._planning_in_progress = True
            text = (user_message or "").strip()
            if len(text) < 20:
                return None
            hints = ["步骤", "先", "然后", "最后", "整个", "完整", "系列", "批量", "规划", "计划", "analyse", "analyze", "plan", "project", "设计", "开发"]
            if not any(h in text.lower() for h in hints):
                return None

            from prism.planner import Planner
            planner = Planner(max_steps=4, max_retries=1)
            plan = planner.decompose(text)
            if len(plan.subtasks) <= 1:
                return None

            logger.info("auto plan: goal=%s steps=%d", text[:50], len(plan.subtasks))
            results = []
            for task in plan.subtasks:
                if plan.status != "active":
                    break
                task.status = "running"
                task.started_at = time.time()
                try:
                    reply = self._execute_subtask(task.description)
                    task.status = "done"
                    task.result = {"success": True, "text": reply}
                    results.append(reply)
                except Exception as exc:
                    failed = planner.mark_failed(plan, task, str(exc))
                    if failed is None:
                        results.append(f"子任务失败: {task.description}")
                        break
                    plan = failed
            summary = planner.summarize(plan)
            return summary
        except (TypeError, AttributeError, Exception):
            logger.debug("auto plan execution failed: %s", traceback.format_exc())
            return None
        finally:
            self._planning_in_progress = False

    def _execute_subtask(self, text: str) -> str:
        """执行子任务：跳过 planning 阶段，直接走正常 chat"""
        saved = self._planning_in_progress
        self._planning_in_progress = True
        try:
            return self.chat(text)
        finally:
            self._planning_in_progress = saved

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
- 如果不确定答案或信息可能过时，明确告诉用户，不要编造。
"""
    
    def _inject_memory_context(self, user_message: str) -> None:
        """
        动态注入记忆上下文：
        1. 身份类固定注入
        2. 对当前 query 主动 recall + 语义召回，最多 3 条
        3. 其余按重要度补位，总记忆条数控制在 5 条内
        """
        try:
            base = (self.system_prompt or "").rstrip()
            # 移除旧记忆块，避免重复堆叠
            if "## 记忆上下文" in base:
                base = base[: base.index("## 记忆上下文")].rstrip()

            with persistent_memory._lock:
                identities = [m for m in persistent_memory._index.values() if m.category == "user_profile"]
                identity_block = ""
                if identities:
                    lines = ["【身份】"]
                    for m in identities[:3]:
                        lines.append(f"- {m.key}: {m.value}")
                    identity_block = "\n" + "\n".join(lines)

                # 主动 recall：先用 recall() 拿高置信度记忆，再做语义召回
                recall_keys = set()
                query_matches = []
                try:
                    for key in (persistent_memory.recall(user_message, limit=3) or []):
                        recall_keys.add(key)
                        mem = persistent_memory._index.get(key)
                        if mem:
                            query_matches.append(mem)
                except (TypeError, AttributeError, Exception):
                    recall_keys = set()

                if not query_matches:
                    query_matches = persistent_memory.search(user_message, category=None, limit=3)

                seen = set()
                query_block = ""
                if query_matches:
                    lines = ["【相关记忆】"]
                    for m in query_matches:
                        if m.key in seen:
                            continue
                        seen.add(m.key)
                        recall_keys.add(m.key)
                        lines.append(f"- [{m.category}] {m.key}: {m.value[:120]}")
                    query_block = "\n" + "\n".join(lines)

                rest = sorted(
                    [m for m in persistent_memory._index.values() if m.category != "user_profile" and m.key not in seen],
                    key=lambda m: persistent_memory._importance(m),
                    reverse=True,
                )[: max(0, 5 - len(query_matches))]
                rest_block = ""
                if rest:
                    lines = []
                    for m in rest:
                        lines.append(f"- [{m.category}] {m.key}: {m.value[:100]}")
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

    def _tool_precheck(self, tool_name: str, kwargs: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """
        工具调用前轻量校验：
        - 危险命令风险提示
        - 基于近期记忆避免明显重复/冲突
        """
        try:
            if tool_name in {"run_terminal", "execute_tool"}:
                command = kwargs.get("command") or kwargs.get("text") or ""
                command_lower = (command or "").lower()
                # 高危命令提示
                dangerous = ["rm -rf /", "rm -rf ~", "rm -rf c:\\", "del /s /q c:\\", "format c:", "shutdown", "reboot", "rm -rf /*", "mkfs"]
                if any(pat in command_lower for pat in dangerous):
                    return {
                        "success": False,
                        "error": f"检测到高危命令，已拦截：{command[:100]}。如需执行请明确确认。",
                        "tool": tool_name,
                    }
            # 基于近期对话记忆检查是否刚刚执行过类似工具调用
            try:
                recent = [m for m in (getattr(self, "messages", []) or [])[-6:]]
                recent_tool_calls = []
                for m in recent:
                    if getattr(m, "role", "") == "assistant" and hasattr(m, "tool_calls"):
                        recent_tool_calls.extend(getattr(m, "tool_calls", []) or [])
                for tc in recent_tool_calls:
                    name = getattr(tc, "name", "") or tc.get("name", "") if isinstance(tc, dict) else ""
                    if name == tool_name:
                        args = getattr(tc, "arguments", {}) or tc.get("arguments", {}) if isinstance(tc, dict) else {}
                        if args == kwargs:
                            return {
                                "success": False,
                                "error": f"刚刚执行过相同的 {tool_name}，为了避免重复，我先跳过。",
                                "tool": tool_name,
                            }
            except Exception:
                pass
            return None
        except Exception:
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

        # 复杂任务自动规划执行
        try:
            plan_result = self._maybe_plan_and_execute(user_message)
            if plan_result is not None:
                return plan_result
        except (TypeError, AttributeError, Exception):
            logger.debug("plan execution failed: %s", traceback.format_exc())

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
        message_id = f"msg_{int(__import__('time').time()*1000)}_{len(self.messages)}"
        user_msg = Message(role="user", content=user_message)
        user_msg.id = message_id
        self.messages.append(user_msg)
        self._trim_messages()
        try:
            from prism.message_store import message_store
            message_store.add(user_msg)
        except Exception:
            pass

        # 在关键操作前自动保存快照（用于 /rollback）
        # 每 5 轮对话保存一次，避免频繁 IO
        if len(self.messages) % 5 == 0:
            try:
                from prism.checkpoint import save_checkpoint
                save_checkpoint(self, label="before_chat")
            except Exception:
                pass
        def _serialize_content(content):
            if isinstance(content, str):
                return content
            if isinstance(content, list):
                serialized = []
                for item in content:
                    if isinstance(item, dict):
                        serialized.append(item)
                    elif isinstance(item, str):
                        serialized.append({"type": "text", "text": item})
                    else:
                        serialized.append({"type": "text", "text": str(item)})
                return serialized
            return str(content)

        api_messages = [
            {"role": m.role, "content": _serialize_content(m.content)}
            for m in self.messages
        ]

        # 如果有流式回调，使用流式请求
        if on_stream is not None:
            result = provider_pool.stream_chat(api_messages, on_chunk=on_stream, **kwargs)
        else:
            result = provider_pool.chat(api_messages)

        if not result.get('success'):
            logger.warning("chat failed: %s", result.get('error'))
            try:
                record_failure(task="chat", error=str(result.get('error', '')), context=user_message)
                for advice in apply_strategies("chat"):
                    logger.debug("self-improvement strategy: %s", advice)
            except (ImportError, Exception):
                pass
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

        # 自动执行工具并继续对话，直到拿到最终文本回复
        try:
            if tool_calls:
                assistant_content = self._auto_tool_loop(api_messages, assistant_content, tool_calls)
        except (TypeError, AttributeError, Exception) as exc:
            logger.debug("auto tool loop failed: %s", traceback.format_exc())

        try:
            from prism.usage import usage_tracker
            usage_tracker.record(
                model=str(result.get('model') or ''),
                prompt_tokens=int(result.get('prompt_tokens') or 0),
                completion_tokens=int(result.get('completion_tokens') or 0),
                latency_ms=float(result.get('latency') or result.get('latency_ms') or 0.0),
                success=True,
                session_id=getattr(self, 'session_id', ''),
            )
        except (ImportError, Exception):
            pass

        # 自我校验：后置检查回复质量
        try:
            if getattr(self, "validation_enabled", False):
                fixed = self._run_self_validation(user_message, assistant_content, tool_calls)
                if fixed is not None:
                    assistant_content = fixed
        except (TypeError, AttributeError, Exception):
            logger.debug("post-validation failed: %s", traceback.format_exc())

        # 添加助手回复
        assistant_content = assistant_content or ""
        assistant_msg = Message(role="assistant", content=assistant_content)
        if hasattr(user_msg, "id") and user_msg.id:
            assistant_msg.id = f"reply_{user_msg.id}"
        self.messages.append(assistant_msg)
        self._trim_messages()
        try:
            from prism.message_store import message_store
            message_store.add(assistant_msg)
        except Exception:
            pass

        # Run after_chat hooks
        hook_manager.run_hooks("after_chat", {
            "message": user_message,
            "response": assistant_content,
            "agent": self,
        })

        # 自动记忆：若开启，则将本轮关键信息写入持久记忆
        if getattr(self, "enable_auto_memory", False):
            try:
                scope = getattr(self, "memory_scope", "default") or "default"
                turn_key = f"chat:{scope}:{datetime.now().isoformat()}"
                turn_value = f"用户: {user_message}\n助手: {assistant_content or '[无回复]'}"
                persistent_memory.remember(turn_key, turn_value, category=f"chat_history:{scope}")
                self._extract_user_facts(user_message, assistant_content or "")
            except (OSError, Exception):
                logger.debug("auto memory save failed: %s", traceback.format_exc())

        # 自动化记忆管理：定期整理、摘要旧对话
        try:
            mgr = getattr(self, "_memory_manager", None)
            if mgr is not None:
                scope = getattr(self, "memory_scope", "default") or "default"
                mgr.on_chat_turn(scope=scope)
        except Exception:
            pass

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
            with self._tool_lock:
                last_time = self._last_executed.get(marker, 0)
                now = datetime.now().timestamp()
                if now - last_time < 60:
                    return {
                        "success": False,
                        "error": f"为避免重复执行，已拦截 {tool_name}（60 秒内相同调用不重跑）",
                        "provider": getattr(self, "name", "local"),
                    }
                self._last_executed[marker] = now

        # 工具调用前预检：基于近期记忆和历史结果做轻量校验
        try:
            precheck = self._tool_precheck(tool_name, kwargs)
            if precheck is not None:
                return precheck
        except Exception:
            pass

        if not self.tools_enabled:
            return {'success': False, 'error': 'Tools disabled'}
        
        try:
            from prism.security import security_manager
            block = security_manager.check(tool_name, kwargs)
            if block:
                return {'success': False, 'error': block}
        except Exception:
            pass
        
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
            try:
                result = registry.execute(tool_name, **kwargs)
            except (TypeError, AttributeError, Exception) as exc:
                result = {"success": False, "error": str(exc)}
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
        
        # 最终失败，写入持久化重试队列
        try:
            from prism.retry_strategy import retry_strategy
            retry_strategy.submit(
                task_id=f"tool:{tool_name}:{len(self.tool_calls)}",
                func=tool_name,
                args=[],
                kwargs=kwargs,
                max_attempts=3,
                backoff=2.0,
            )
        except Exception:
            pass
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

    def _auto_tool_loop(
        self,
        api_messages: List[Dict[str, Any]],
        assistant_content: str,
        tool_calls: List[Dict[str, Any]],
    ) -> str:
        """自动执行工具并继续对话，直到拿到最终文本回复。"""
        try:
            import json as _json
        except Exception:
            _json = None

        content = assistant_content or ""
        current_messages = list(api_messages)

        for attempt in range(5):
            results = []
            for tc in tool_calls:
                name = tc.get('name') or tc.get('function', {}).get('name')
                args = tc.get('arguments') or tc.get('function', {}).get('arguments') or {}
                if isinstance(args, str):
                    try:
                        args = _json.loads(args) if _json else {}
                    except Exception:
                        args = {"text": args}
                result = self.execute_tool(name, **args)
                results.append((name, result))

            for name, result in results:
                self._append_tool_message(name, result)

            current_messages = [
                {"role": m.role, "content": m.content or ""}
                for m in self.messages
            ]

            try:
                follow = provider_pool.chat(current_messages)
            except Exception:
                break

            if not follow.get('success'):
                break

            next_content = follow.get('content', '') or ''
            next_tool_calls = follow.get('tool_calls') or []

            if next_content and not next_tool_calls:
                return next_content

            if not next_tool_calls:
                return next_content or content

            content = next_content
            tool_calls = next_tool_calls

        return content

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

    def rename_session(self, old_name: str, new_name: str) -> bool:
        """重命名会话"""
        if not old_name or not new_name or old_name == new_name:
            return False
        session_dir = getattr(self, "session_dir", None) or Path.home() / ".prism" / "sessions"
        src = session_dir / f"{old_name}.json"
        dst = session_dir / f"{new_name}.json"
        if not src.exists():
            return False
        if dst.exists():
            return False
        try:
            payload = json.loads(src.read_text(encoding="utf-8"))
            dst.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
            src.unlink()
            return True
        except Exception:
            logger.debug("rename session failed: %s", traceback.format_exc())
            return False




    # ========== 记忆系统 ==========
    def _extract_user_facts(self, user_message: str, assistant_content: str) -> None:
        """规则提取：用户称呼、偏好、事实、任务、时间、地点等。"""
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
            (r"我的([^，。]{1,20})是([^，。]{1,20})", "user_profile", "attribute"),
            (r"我住在([^，。]{1,20})", "user_profile", "location"),
            (r"我的([^，。]{1,10})是([^，。]{1,20})", "user_profile", "fact"),
            (r"请记住([^，。]{1,30})", "user_profile", "fact"),
            (r"别忘了([^，。]{1,30})", "user_profile", "fact"),
            (r"我在做([^，。]{1,20})", "user_context", "task"),
            (r"正在做([^，。]{1,20})", "user_context", "task"),
            (r"下周([^，。]{1,20})", "user_context", "plan"),
            (r"明天([^，。]{1,20})", "user_context", "plan"),
            (r"提醒我([^，。]{1,20})", "user_context", "reminder"),
        ]
        for pattern, category, key in patterns:
            m = re.search(pattern, combined)
            if m:
                value = m.group(1).strip().strip(chr(10) + chr(13) + "，。,.:; ")
                if value and len(value) <= 30:
                    try:
                        persistent_memory.remember(key, value, category=category, confidence=0.85)
                    except Exception:
                        pass
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
