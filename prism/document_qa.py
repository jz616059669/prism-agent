"""
PRISM Agent - Document Q&A
上传文档后直接问答，RAG 增强
"""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)

_DOC_DIR = Path.home() / ".prism" / "docs"
_DOC_DIR.mkdir(parents=True, exist_ok=True)


@dataclass
class Document:
    id: str
    name: str = ""
    text: str = ""
    chunks: List[str] = field(default_factory=list)
    created_at: float = field(default_factory=lambda: __import__("time").time())

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "name": self.name,
            "text": self.text,
            "chunks": list(self.chunks),
            "created_at": self.created_at,
        }


class DocumentQA:
    def __init__(self, chunk_size: int = 500, overlap: int = 80) -> None:
        self.chunk_size = chunk_size
        self.overlap = overlap
        self._docs: Dict[str, Document] = {}
        self._load()

    def _load(self) -> None:
        for doc_file in _DOC_DIR.glob("*.json"):
            try:
                data = json.loads(doc_file.read_text(encoding="utf-8"))
                doc = Document(**data)
                self._docs[doc.id] = doc
            except Exception:
                continue

    def ingest(self, name: str, text: str) -> Document:
        doc_id = f"doc_{int(__import__('time').time())}"
        chunks = self._chunk(text)
        doc = Document(id=doc_id, name=name, text=text, chunks=chunks)
        self._docs[doc_id] = doc
        self._save(doc)
        return doc

    def ask(self, question: str, top_k: int = 3) -> Dict[str, Any]:
        question_lower = (question or "").lower()
        scored: List[tuple[float, Document]] = []
        for doc in self._docs.values():
            score = self._score(question_lower, doc)
            scored.append((score, doc))
        scored.sort(key=lambda x: x[0], reverse=True)
        best = [doc for _, doc in scored[:top_k] if _ > 0.0]
        return {
            "question": question,
            "matches": [d.to_dict() for d in best],
            "answer": "\n".join(d.chunks[:2] for d in best),
        }

    def _chunk(self, text: str) -> List[str]:
        chunks: List[str] = []
        start = 0
        text = text or ""
        while start < len(text):
            end = start + self.chunk_size
            chunk = text[start:end]
            chunks.append(chunk)
            start = end - self.overlap
        return chunks

    def _score(self, question: str, doc: Document) -> float:
        if not question or not doc.chunks:
            return 0.0
        score = 0.0
        for chunk in doc.chunks:
            overlap = len(set(question.split()) & set(chunk.lower().split()))
            if overlap:
                score += overlap / max(1, len(question.split()))
        return score

    def list_docs(self) -> List[Dict[str, Any]]:
        return [d.to_dict() for d in self._docs.values()]

    def _save(self, doc: Document) -> None:
        try:
            (_DOC_DIR / f"{doc.id}.json").write_text(
                json.dumps(doc.to_dict(), ensure_ascii=False, indent=2),
                encoding="utf-8",
            )
        except Exception:
            pass


document_qa = DocumentQA()
