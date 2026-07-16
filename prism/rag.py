"""
PRISM Agent - RAG 本地知识库
对本地文档目录建索引，按语义检索相关片段并注入 Agent 上下文
"""

from __future__ import annotations

import hashlib
import json
import logging
import re
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

logger = logging.getLogger(__name__)

_DEFAULT_CHUNK_SIZE = 600
_DEFAULT_OVERLAP = 120


def _chunk_text(text: str, chunk_size: int = _DEFAULT_CHUNK_SIZE, overlap: int = _DEFAULT_OVERLAP) -> List[str]:
    text = text.replace("\r\n", "\n").replace("\r", "\n")
    chunks: List[str] = []
    start = 0
    length = len(text)
    while start < length:
        end = min(start + chunk_size, length)
        chunk = text[start:end]
        if chunk.strip():
            chunks.append(chunk)
        if end >= length:
            break
        start = max(start + chunk_size - overlap, end - overlap)
    return chunks


class LocalRAG:
    """
    本地 RAG：扫描目录 -> 切分 -> 可选 embedding -> 检索
    """

    def __init__(self, root: Optional[str] = None, chunk_size: int = _DEFAULT_CHUNK_SIZE, overlap: int = _DEFAULT_OVERLAP):
        self.root = Path(root).expanduser() if root else Path.home() / ".prism" / "rag"
        self.chunk_size = chunk_size
        self.overlap = overlap
        self._index_file = self.root / ".prism_rag_index.json"
        self._docs: List[Dict[str, Any]] = []
        self._load_index()

    def _load_index(self) -> None:
        if self._index_file.exists():
            try:
                data = json.loads(self._index_file.read_text(encoding="utf-8"))
                if isinstance(data, list):
                    self._docs = data
            except Exception as exc:
                logger.debug("rag index load failed: %s", exc)
                self._docs = []

    def _save_index(self) -> None:
        try:
            self._index_file.write_text(json.dumps(self._docs, ensure_ascii=False, indent=2), encoding="utf-8")
        except Exception as exc:
            logger.debug("rag index save failed: %s", exc)

    def _file_hash(self, path: Path) -> str:
        h = hashlib.sha256()
        with path.open("rb") as f:
            for chunk in iter(lambda: f.read(65536), b""):
                h.update(chunk)
        return h.hexdigest()

    def _iter_files(self) -> List[Path]:
        if not self.root.exists() or not self.root.is_dir():
            return []
        return [p for p in self.root.rglob("*") if p.is_file() and p.suffix.lower() in {".md", ".txt", ".json", ".yaml", ".yml"}]

    def build(self) -> Dict[str, Any]:
        files = self._iter_files()
        new_docs: List[Dict[str, Any]] = []
        total_chunks = 0
        for path in files:
            try:
                rel = str(path.relative_to(self.root))
                sha = self._file_hash(path)
                existing = next((d for d in self._docs if d.get("path") == rel and d.get("sha") == sha), None)
                if existing:
                    new_docs.append(existing)
                    continue
                text = path.read_text(encoding="utf-8", errors="ignore")
                chunks = _chunk_text(text, self.chunk_size, self.overlap)
                new_docs.append({
                    "path": rel,
                    "sha": sha,
                    "size": path.stat().st_size,
                    "chunks": [
                        {"id": f"{rel}:::{idx}", "text": c, "embedding": None}
                        for idx, c in enumerate(chunks)
                    ],
                })
                total_chunks += len(chunks)
            except Exception as exc:
                logger.debug("rag build skip %s: %s", path, exc)
        self._docs = new_docs
        self._save_index()
        return {"success": True, "files": len(new_docs), "chunks": total_chunks}

    def refresh(self) -> Dict[str, Any]:
        return self.build()

    def _embed(self, text: str) -> Optional[List[float]]:
        try:
            from prism.memory import persistent_memory
            vec = persistent_memory._embed(text)
            if vec:
                return [float(x) for x in vec]
        except Exception as exc:
            logger.debug("rag embed failed: %s", exc)
        return None

    def _cosine(self, a: List[float], b: List[float]) -> float:
        import math
        if not a or not b or len(a) != len(b):
            return 0.0
        dot = sum(x * y for x, y in zip(a, b))
        na = math.sqrt(sum(x * x for x in a))
        nb = math.sqrt(sum(x * x for x in b))
        if na <= 0 or nb <= 0:
            return 0.0
        return dot / (na * nb)

    def _ensure_embeddings(self, doc: Dict[str, Any]) -> None:
        for chunk in doc.get("chunks", []):
            if chunk.get("embedding") is None:
                chunk["embedding"] = self._embed(chunk.get("text", ""))

    def query(self, text: str, top_k: int = 3) -> List[Dict[str, Any]]:
        qvec = self._embed(text)
        if not qvec:
            return []
        scored: List[Tuple[float, Dict[str, Any]]] = []
        for doc in self._docs:
            self._ensure_embeddings(doc)
            for chunk in doc.get("chunks", []):
                vec = chunk.get("embedding")
                if not vec:
                    continue
                score = self._cosine(qvec, vec)
                scored.append((score, {"path": doc.get("path"), "text": chunk.get("text"), "score": round(score, 4)}))
        scored.sort(key=lambda x: x[0], reverse=True)
        return [item for _, item in scored[: max(1, top_k)]]

    def query_keyword(self, text: str, top_k: int = 3) -> List[Dict[str, Any]]:
        q = re.split(r"\s+", (text or "").strip())
        q = [t for t in q if t]
        if not q:
            return []
        scored: List[Tuple[float, Dict[str, Any]]] = []
        for doc in self._docs:
            for chunk in doc.get("chunks", []):
                hay = chunk.get("text", "")
                score = sum(1 for t in q if t in hay)
                if score > 0:
                    scored.append((score, {"path": doc.get("path"), "text": hay, "score": round(score / max(1, len(q)), 4)}))
        scored.sort(key=lambda x: x[0], reverse=True)
        return [item for _, item in scored[: max(1, top_k)]]

    def stats(self) -> Dict[str, Any]:
        total_chunks = sum(len(d.get("chunks", [])) for d in self._docs)
        return {"files": len(self._docs), "chunks": total_chunks, "root": str(self.root)}
