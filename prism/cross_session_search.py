"""
PRISM Agent - 跨 Session 记忆搜索
跨历史会话检索，不止当前 session
"""

from __future__ import annotations

import json
import logging
from collections import Counter
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)

_MEMORY_DIR = Path.home() / ".prism" / "memory"


@dataclass
class CrossMemoryResult:
    session_id: str
    content: str = ""
    score: float = 0.0
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "session_id": self.session_id,
            "content": self.content,
            "score": self.score,
            "metadata": self.metadata,
        }


class CrossSessionSearch:
    def search(self, query: str, top_k: int = 5) -> List[CrossMemoryResult]:
        results: List[CrossMemoryResult] = []
        if not _MEMORY_DIR.exists():
            return results
        query_tokens = self._tokenize(query)
        for memory_file in _MEMORY_DIR.glob("*.jsonl"):
            try:
                session_id = memory_file.stem
                for line in memory_file.read_text(encoding="utf-8").splitlines():
                    if not line.strip():
                        continue
                    try:
                        record = json.loads(line)
                    except Exception:
                        continue
                    content = str(record.get("value", "") or record.get("content", "") or "")
                    if not content:
                        continue
                    score = self._score(query_tokens, content)
                    if score > 0:
                        results.append(CrossMemoryResult(session_id=session_id, content=content[:300], score=score, metadata={"key": record.get("key", "")}))
            except Exception:
                continue
        results.sort(key=lambda r: r.score, reverse=True)
        return results[:top_k]

    def _tokenize(self, text: str) -> List[str]:
        return [word.lower() for line in (text or "").splitlines() for word in line.split() if word.isalnum()]

    def _score(self, query_tokens: List[str], content: str) -> float:
        content_tokens = self._tokenize(content)
        tf = Counter(content_tokens)
        score = 0.0
        for token in query_tokens:
            if token in tf:
                score += tf[token]
        return score


cross_session_search = CrossSessionSearch()
