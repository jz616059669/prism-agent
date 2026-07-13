"""
PRISM Agent - 知识库问答
自定义知识库问答
"""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)

_KB_DIR = Path.home() / ".prism" / "knowledge"
_KB_DIR.mkdir(parents=True, exist_ok=True)


@dataclass
class KnowledgeEntry:
    id: str
    question: str = ""
    answer: str = ""
    tags: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "question": self.question,
            "answer": self.answer,
            "tags": list(self.tags),
        }


class KnowledgeBaseQA:
    def __init__(self) -> None:
        self._entries: Dict[str, KnowledgeEntry] = {}
        self._load()

    def _load(self) -> None:
        for entry_file in _KB_DIR.glob("*.json"):
            try:
                data = json.loads(entry_file.read_text(encoding="utf-8"))
                entry = KnowledgeEntry(**data)
                self._entries[entry.id] = entry
            except Exception:
                continue

    def add(self, question: str, answer: str, tags: Optional[List[str]] = None) -> KnowledgeEntry:
        entry_id = f"kb_{int(__import__('time').time())}"
        entry = KnowledgeEntry(id=entry_id, question=question, answer=answer, tags=tags or [])
        self._entries[entry_id] = entry
        self._save(entry)
        return entry

    def ask(self, question: str, top_k: int = 3) -> Dict[str, Any]:
        q = (question or "").lower()
        scored = []
        for entry in self._entries.values():
            score = 0.0
            if q in entry.question.lower():
                score += 2.0
            for tag in entry.tags:
                if tag.lower() in q:
                    score += 1.0
            scored.append((score, entry))
        scored.sort(key=lambda x: x[0], reverse=True)
        best = [entry for score, entry in scored[:top_k] if score > 0]
        return {
            "question": question,
            "matches": [e.to_dict() for e in best],
            "answer": best[0].answer if best else "",
        }

    def list_entries(self) -> List[Dict[str, Any]]:
        return [e.to_dict() for e in self._entries.values()]

    def _save(self, entry: KnowledgeEntry) -> None:
        try:
            (_KB_DIR / f"{entry.id}.json").write_text(
                json.dumps(entry.to_dict(), ensure_ascii=False, indent=2),
                encoding="utf-8",
            )
        except Exception:
            pass


knowledge_base_qa = KnowledgeBaseQA()
