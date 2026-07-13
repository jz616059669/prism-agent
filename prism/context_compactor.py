"""
PRISM Agent - 智能上下文裁剪
对话过长时自动提炼关键信息，防 token 爆炸
"""

from __future__ import annotations

import json
import logging
import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)

_CTX_DIR = Path.home() / ".prism" / "context"
_CTX_DIR.mkdir(parents=True, exist_ok=True)


@dataclass
class ContextSummary:
    session_id: str
    summary: str = ""
    message_count: int = 0
    token_count: int = 0
    created_at: float = field(default_factory=lambda: __import__("time").time())

    def to_dict(self) -> Dict[str, Any]:
        return {
            "session_id": self.session_id,
            "summary": self.summary,
            "message_count": self.message_count,
            "token_count": self.token_count,
            "created_at": self.created_at,
        }


class ContextCompactor:
    def __init__(self, max_tokens: int = 6000, max_messages: int = 40) -> None:
        self.max_tokens = max(max_tokens, 500)
        self.max_messages = max(max_messages, 5)

    def should_compact(self, messages: List[Dict[str, Any]]) -> bool:
        token_count = sum(len(str(m.get("content", "") or "")) for m in messages)
        return len(messages) > self.max_messages or token_count > self.max_tokens

    def compact(self, session_id: str, messages: List[Dict[str, Any]]) -> ContextSummary:
        summary_text = self._summarize(messages)
        summary = ContextSummary(session_id=session_id, summary=summary_text, message_count=len(messages), token_count=sum(len(str(m.get("content", "") or "")) for m in messages))
        try:
            (_CTX_DIR / f"{session_id}.json").write_text(
                json.dumps(summary.to_dict(), ensure_ascii=False, indent=2),
                encoding="utf-8",
            )
        except Exception:
            pass
        return summary

    def _summarize(self, messages: List[Dict[str, Any]]) -> str:
        parts: List[str] = []
        for msg in messages[-10:]:
            role = msg.get("role", "user")
            content = str(msg.get("content", "") or "")
            parts.append(f"[{role}] {content[:180]}")
        return "\n".join(parts)


context_compactor = ContextCompactor()
