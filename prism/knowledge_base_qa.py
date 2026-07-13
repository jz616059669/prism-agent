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
                entry.embeddings = [self._embed(entry.question + " " + entry.answer)]
                self._entries[entry.id] = entry
            except Exception:
                continue

    def add(self, question: str, answer: str, tags: Optional[List[str]] = None) -> KnowledgeEntry:
        entry_id = f"kb_{int(__import__('time').time())}"
        entry = KnowledgeEntry(id=entry_id, question=question, answer=answer, tags=tags or [])
        entry.embeddings = [self._embed(question + " " + answer)]
        self._entries[entry_id] = entry
        self._save(entry)
        return entry

    def ask(self, question: str, top_k: int = 3) -> Dict[str, Any]:
        q = (question or "").lower()
        q_emb = self._embed(question)
        scored = []
        for entry in self._entries.values():
            score = self._score_embedding(q_emb, entry)
            if not score:
                score = self._score_text(q, entry)
            scored.append((score, entry))
        scored.sort(key=lambda x: x[0], reverse=True)
        best = [entry for score, entry in scored[:top_k] if score > 0.0]
        return {
            "question": question,
            "matches": [e.to_dict() for e in best],
            "answer": best[0].answer if best else "",
        }

    def _score_text(self, q: str, entry: KnowledgeEntry) -> float:
        score = 0.0
        if q in entry.question.lower():
            score += 2.0
        for tag in entry.tags:
            if tag.lower() in q:
                score += 1.0
        return score

    def _embed(self, text: str) -> List[float]:
        text = text or ""
        if not text.strip():
            return []
        vec = [0.0] * 16
        for i, ch in enumerate(text[:64]):
            vec[i % 16] += (ord(ch) % 97) / 97.0
        norm = sum(v * v for v in vec) ** 0.5 or 1.0
        return [v / norm for v in vec]

    def _cosine(self, a: List[float], b: List[float]) -> float:
        if not a or not b or len(a) != len(b):
            return 0.0
        return sum(x * y for x, y in zip(a, b))

    def _score_embedding(self, q_emb: List[float], entry: KnowledgeEntry) -> float:
        if not q_emb or not getattr(entry, "embeddings", []):
            return 0.0
        best = 0.0
        for emb in entry.embeddings:
            best = max(best, self._cosine(q_emb, emb))
        return best

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
