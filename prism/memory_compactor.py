"""
PRISM Agent - Memory 自动压缩
长期记忆定期提炼摘要，防止 ~/.prism/memory 无限膨胀
"""

from __future__ import annotations

import logging
import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)

_MEMORY_DIR = Path.home() / ".prism" / "memory"
_MEMORY_DIR.mkdir(parents=True, exist_ok=True)


@dataclass
class MemorySummary:
    category: str
    summary: str = ""
    source_count: int = 0
    created_at: float = field(default_factory=lambda: __import__("time").time())

    def to_dict(self) -> Dict[str, Any]:
        return {
            "category": self.category,
            "summary": self.summary,
            "source_count": self.source_count,
            "created_at": self.created_at,
        }


class MemoryCompactor:
    def __init__(self, max_items: int = 200, max_chars: int = 12_000) -> None:
        self.max_items = max(max_items, 10)
        self.max_chars = max(max_chars, 500)

    def compact_category(self, category: str, items: List[Dict[str, Any]]) -> Optional[MemorySummary]:
        if len(items) <= self.max_items and sum(len(str(i)) for i in items) <= self.max_chars:
            return None
        summary_lines: List[str] = []
        for item in items[:10]:
            value = str(item.get("value", "") or item.get("content", "") or "")
            summary_lines.append(value[:200])
        summary_text = "\n".join(summary_lines)
        summary = MemorySummary(category=category, summary=summary_text, source_count=len(items))
        try:
            (_MEMORY_DIR / f"{category}_summary.json").write_text(
                __import__("json").dumps(summary.to_dict(), ensure_ascii=False, indent=2),
                encoding="utf-8",
            )
        except Exception:
            pass
        return summary

    def compact_all(self) -> List[MemorySummary]:
        summaries: List[MemorySummary] = []
        try:
            for memory_file in _MEMORY_DIR.glob("*.jsonl"):
                try:
                    lines = [line for line in memory_file.read_text(encoding="utf-8").splitlines() if line.strip()]
                    if len(lines) <= self.max_items:
                        continue
                    data = [__import__("json").loads(line) for line in lines]
                    category = memory_file.stem
                    summary = self.compact_category(category, data)
                    if summary:
                        summaries.append(summary)
                except Exception:
                    continue
        except Exception:
            pass
        return summaries


memory_compactor = MemoryCompactor()
