"""
PRISM Agent - 自动摘要生成
长对话/文档自动提炼摘要
"""

from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional

from prism.context_compactor import context_compactor

logger = logging.getLogger(__name__)


class AutoSummarizer:
    def summarize_messages(self, session_id: str, messages: List[Dict[str, Any]]) -> Dict[str, Any]:
        if not context_compactor.should_compact(messages):
            return {"compacted": False, "summary": ""}
        summary = context_compactor.compact(session_id=session_id, messages=messages)
        return {"compacted": True, "summary": summary.summary, "message_count": summary.message_count, "token_count": summary.token_count}

    def summarize_text(self, text: str, max_chars: int = 500) -> str:
        if not text:
            return ""
        lines = [line.strip() for line in text.splitlines() if line.strip()]
        if len(lines) <= 5:
            return "\n".join(lines[: max_chars // 10])
        return "\n".join(lines[:5]) + "\n...\n" + "\n".join(lines[-3:])


auto_summarizer = AutoSummarizer()
