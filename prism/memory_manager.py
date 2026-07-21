"""
PRISM 自动化记忆管理（类 Hermes 记忆自动整理）
职责：
1. 定期整理记忆库（合并重复、压缩超长、清理过期）
2. 将旧对话摘要自动提炼为高阶事实
3. 按 persona scope 隔离整理
"""
from __future__ import annotations

import threading
import time
from dataclasses import dataclass
from typing import Any, Dict, List, Optional

from prism.memory import PersistentMemory


@dataclass
class MemoryManagerConfig:
    enable: bool = True
    compact_interval_turns: int = 20
    summarize_after_days: int = 7
    max_chat_history_per_scope: int = 30
    max_total_entries: int = 200
    confidence_cleanup_days: int = 30
    low_confidence_threshold: float = 0.3
    lock: threading.Lock = threading.Lock()


class MemoryManager:
    def __init__(
        self,
        memory: PersistentMemory,
        config: Optional[MemoryManagerConfig] = None,
    ) -> None:
        self.memory = memory
        self.config = config or MemoryManagerConfig()
        self._turn_count: Dict[str, int] = {}
        self._last_compact: Dict[str, float] = {}
        self._lock = threading.Lock()

    def on_chat_turn(self, scope: str = "default") -> None:
        if not self.config.enable:
            return
        scope_key = scope or "default"
        with self._lock:
            self._turn_count[scope_key] = self._turn_count.get(scope_key, 0) + 1
            turns = self._turn_count[scope_key]
        if turns % max(1, self.config.compact_interval_turns) != 0:
            return
        self.compact(scope=scope_key)

    def compact(self, scope: str = "default") -> Dict[str, Any]:
        scope_key = scope or "default"
        with self._lock:
            self._last_compact[scope_key] = time.time()
        try:
            chat_prefix = f"chat_history:{scope_key}"
            chat_entries = [
                m for m in self.memory._index.values()
                if m.category == chat_prefix
            ]
            chat_entries.sort(key=lambda m: getattr(m, "created_at", "") or "")
            if len(chat_entries) > self.config.max_chat_history_per_scope:
                excess = chat_entries[: len(chat_entries) - self.config.max_chat_history_per_scope]
                for m in excess:
                    key = m.key
                    try:
                        self.memory.forget(key)
                    except Exception:
                        pass
            summary = self.memory.compact(max_entries=self.config.max_total_entries)
            # 自动提炼旧对话为高阶摘要
            try:
                self.summarize_old_chats(scope=scope_key)
            except Exception:
                pass
            return {
                "scope": scope_key,
                "compacted": True,
                "summary": summary,
            }
        except Exception:
            return {"scope": scope_key, "compacted": False}

    def summarize_old_chats(self, scope: str = "default") -> Optional[str]:
        scope_key = scope or "default"
        chat_prefix = f"chat_history:{scope_key}"
        try:
            entries = [
                m for m in self.memory._index.values()
                if m.category == chat_prefix
            ]
            entries.sort(key=lambda m: getattr(m, "created_at", "") or "")
            if len(entries) < 5:
                return None
            cutoff = time.time() - self.config.summarize_after_days * 86400
            from datetime import datetime
            old = []
            for m in entries:
                ts = getattr(m, "created_at", "") or getattr(m, "updated_at", "") or ""
                if not ts:
                    continue
                try:
                    dt = datetime.fromisoformat(ts)
                    if dt.timestamp() < cutoff:
                        old.append(m)
                except Exception:
                    pass
            if not old:
                return None
            # 优先用 LLM 提炼摘要；失败则回退到简单拼接
            summary_text = self._llm_summarize(old, scope=scope_key)
            if not summary_text:
                lines: List[str] = []
                for m in old:
                    v = getattr(m, "value", "") or ""
                    v = v.replace("\n", " ")
                    if len(v) > 80:
                        v = v[:77] + "..."
                    lines.append(f"- {v}")
                summary_text = "\n".join(lines)
            if summary_text:
                try:
                    self.memory.remember(
                        f"chat_summary:{scope_key}:{int(time.time())}",
                        summary_text,
                        category=f"chat_summary:{scope_key}",
                        confidence=0.75,
                    )
                except Exception:
                    pass
                for m in old:
                    try:
                        self.memory.forget(m.key)
                    except Exception:
                        pass
                return summary_text
        except Exception:
            pass
        return None

    def _llm_summarize(self, entries: List[Any], scope: str = "default") -> Optional[str]:
        """用 LLM 将多条旧对话压缩为一段高阶摘要。"""
        try:
            from prism.providers.manager import provider_pool
        except Exception:
            return None
        lines: List[str] = []
        for m in entries[:20]:
            v = getattr(m, "value", "") or ""
            v = v.replace("\n", " ")
            if len(v) > 120:
                v = v[:117] + "..."
            lines.append(v)
        if not lines:
            return None
        prompt = (
            "你是 PRISM 的记忆提炼器。请将以下旧对话压缩为一段高阶摘要，"
            "只保留关键事实、用户偏好、未完成事项，控制在 300 字以内。\n\n"
            + "\n".join(lines)
        )
        try:
            result = provider_pool.chat([
                {"role": "system", "content": "只输出摘要，不要解释。"},
                {"role": "user", "content": prompt},
            ])
            content = (result or {}).get("content", "") or ""
            return content.strip()[:500]
        except Exception:
            return None


memory_manager = MemoryManager(memory=PersistentMemory())
