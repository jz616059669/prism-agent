"""
PRISM Agent - Enhanced Persistent Memory
基础 KV 记忆 + 可选语义检索 + 记忆摘要压缩
"""

from __future__ import annotations

import json
import logging
import traceback
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from prism.paths import memory_dir

logger = logging.getLogger("prism.memory")


@dataclass
class Memory:
    """记忆条目"""
    key: str
    value: str
    category: str = "general"
    confidence: float = 1.0
    source: str = "user"
    created_at: str = ""
    updated_at: str = ""
    embedding: Optional[List[float]] = None
    embedding_model: str = ""
    access_count: int = 0
    last_accessed_at: str = ""


class _EmbeddingClient:
    """基于现有 OpenAIProvider 的 embedding 客户端，零额外依赖。"""

    def __init__(self, base_url: str, api_key: str, model: str, timeout: int = 60) -> None:
        try:
            from openai import OpenAI
            import httpx
        except ImportError as exc:
            raise ImportError(
                "MemoryEmbeddingIndex 需要 openai 和 httpx，"
                "请执行 `pip install openai httpx`。"
            ) from exc
        self._client = OpenAI(
            base_url=base_url.rstrip("/"),
            api_key=api_key,
            http_client=httpx.Client(timeout=timeout),
        )
        self._model = model

    def embed(self, text: str) -> Optional[List[float]]:
        try:
            resp = self._client.embeddings.create(
                model=self._model,
                input=text,
            )
            return resp.data[0].embedding
        except Exception as exc:
            logger.debug("embedding failed: %s", exc)
            return None


class MemoryEmbeddingIndex:
    """轻量语义索引：向量存在磁盘，不占内存。"""

    def __init__(self, base_dir: Optional[Path] = None) -> None:
        self.base_dir = Path(base_dir) if base_dir is not None else memory_dir()
        self.base_dir.mkdir(parents=True, exist_ok=True)
        self._index_path = self.base_dir / "embeddings.json"
        self._client: Optional[_EmbeddingClient] = None
        self._model: str = ""
        self._vectors: Dict[str, List[float]] = {}
        self._load()

    def configure(self, base_url: str, api_key: str, model: str) -> None:
        self._client = _EmbeddingClient(base_url=base_url, api_key=api_key, model=model)
        self._model = model

    def _load(self) -> None:
        if not self._index_path.exists():
            return
        try:
            data = json.loads(self._index_path.read_text(encoding="utf-8"))
            self._vectors = {k: v for k, v in data.get("vectors", {}).items() if isinstance(v, list)}
        except Exception as exc:
            logger.debug("load memory index failed: %s", traceback.format_exc())
            self._vectors = {}

    def _save(self) -> None:
        try:
            self._index_path.write_text(
                json.dumps({"vectors": self._vectors, "model": self._model}, ensure_ascii=False, indent=2),
                encoding="utf-8",
            )
        except Exception as exc:
            logger.debug("memory index save failed: %s", traceback.format_exc())

    @staticmethod
    def _cosine(a: List[float], b: List[float]) -> float:
        if not a or not b or len(a) != len(b):
            return 0.0
        dot = sum(x * y for x, y in zip(a, b))
        na = sum(x * x for x in a) ** 0.5
        nb = sum(y * y for y in b) ** 0.5
        if na == 0 or nb == 0:
            return 0.0
        return dot / (na * nb)

    def upsert(self, key: str, text: str) -> None:
        if not self._client:
            return
        vec = self._client.embed(text)
        if vec is not None:
            self._vectors[key] = vec
            self._save()

    def remove(self, key: str) -> None:
        self._vectors.pop(key, None)
        self._save()

    def search(self, query: str, top_k: int = 5) -> List[Tuple[str, float]]:
        if not self._client or not self._vectors:
            return []
        qvec = self._client.embed(query)
        if qvec is None:
            return []
        scored = [(k, self._cosine(qvec, v)) for k, v in self._vectors.items()]
        scored.sort(key=lambda x: x[1], reverse=True)
        return scored[:top_k]

    def clear(self) -> None:
        self._vectors.clear()
        self._save()


class PersistentMemory:
    """持久化记忆系统"""

    def __init__(self, base_dir: Optional[Path] = None) -> None:
        self.base_dir = Path(base_dir) if base_dir is not None else memory_dir()
        self.base_dir.mkdir(parents=True, exist_ok=True)
        self._index: Dict[str, Memory] = {}
        self._embedding_index = MemoryEmbeddingIndex(self.base_dir)
        self.decay_half_life_days: Optional[float] = None
        self.decay_min_confidence: float = 0.1
        self._load()

    def _load(self) -> None:
        index_file = self.base_dir / "index.json"
        if not index_file.exists():
            return
        try:
            data = json.loads(index_file.read_text(encoding="utf-8"))
            for item in data.get("memories", []):
                memory = Memory(
                    key=item["key"],
                    value=item["value"],
                    category=item.get("category", "general"),
                    confidence=item.get("confidence", 1.0),
                    source=item.get("source", "user"),
                    created_at=item.get("created_at", ""),
                    updated_at=item.get("updated_at", ""),
                    embedding=item.get("embedding"),
                    embedding_model=item.get("embedding_model", ""),
                    access_count=int(item.get("access_count", 0)),
                    last_accessed_at=item.get("last_accessed_at", ""),
                )
                self._index[memory.key] = memory
                if memory.embedding:
                    self._embedding_index._vectors[memory.key] = memory.embedding
        except Exception as exc:
            logger.warning("failed to load memory: %s", exc)

    def _save(self) -> None:
        index_file = self.base_dir / "index.json"
        data = {
            "memories": [
                {
                    "key": m.key,
                    "value": m.value,
                    "category": m.category,
                    "confidence": m.confidence,
                    "source": m.source,
                    "created_at": m.created_at,
                    "updated_at": m.updated_at,
                    "embedding": m.embedding,
                    "embedding_model": m.embedding_model,
                    "access_count": m.access_count,
                    "last_accessed_at": m.last_accessed_at,
                }
                for m in self._index.values()
            ]
        }
        try:
            index_file.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
        except Exception as exc:
            logger.warning("failed to save memory: %s", exc)

    def configure_embeddings(self, base_url: str, api_key: str, model: str) -> None:
        """启用语义检索。未调用时退化为纯字符串匹配。"""
        self._embedding_index.configure(base_url, api_key, model)

    def remember(
        self,
        key: str,
        value: str,
        category: str = "general",
        confidence: float = 1.0,
        source: str = "user",
    ) -> None:
        from datetime import datetime

        now = datetime.now().isoformat()
        if key in self._index:
            memory = self._index[key]
            memory.value = value
            memory.confidence = max(memory.confidence, confidence)
            memory.updated_at = now
        else:
            memory = Memory(
                key=key,
                value=value,
                category=category,
                confidence=confidence,
                source=source,
                created_at=now,
                updated_at=now,
                access_count=0,
                last_accessed_at="",
            )
        memory.access_count = int(memory.access_count) + 1
        memory.last_accessed_at = now
        self._index[key] = memory
        self._embedding_index.upsert(key, f"{key}: {value}")
        self._save()
        logger.debug("memory stored: %s", key)

    def recall(self, key: str) -> Optional[str]:
        memory = self._index.get(key)
        if memory:
            memory.access_count = int(memory.access_count) + 1
            from datetime import datetime
            memory.last_accessed_at = datetime.now().isoformat()
            return memory.value
        return None

    def forget(self, key: str) -> bool:
        if key in self._index:
            del self._index[key]
            self._embedding_index.remove(key)
            self._save()
            return True
        return False

    def _apply_decay(self) -> None:
        """按时间衰减调整 confidence。"""
        if self.decay_half_life_days is None:
            return
        from datetime import datetime
        now = datetime.now()
        for memory in self._index.values():
            if memory.confidence <= self.decay_min_confidence:
                continue
            created = memory.created_at or memory.updated_at
            if not created:
                continue
            try:
                created_dt = datetime.fromisoformat(created)
                days = max((now - created_dt).total_seconds() / 86400.0, 0.0)
            except Exception:
                continue
            if days <= 0:
                continue
            decay = 2 ** (-days / float(self.decay_half_life_days))
            memory.confidence = max(self.decay_min_confidence, memory.confidence * decay)
            if memory.confidence < 1.0:
                memory.updated_at = now.isoformat()

    def search(
        self,
        query: str,
        category: Optional[str] = None,
        limit: int = 10,
    ) -> List[Memory]:
        self._apply_decay()
        query_lower = query.lower()
        candidates: List[Memory] = []
        for memory in self._index.values():
            if category and memory.category != category:
                continue
            if query_lower in memory.key.lower() or query_lower in memory.value.lower():
                candidates.append(memory)

        semantic_hits = self._embedding_index.search(query, top_k=max(limit, 10))
        semantic_keys = {k for k, _ in semantic_hits}
        if semantic_keys:
            for key in semantic_keys:
                memory = self._index.get(key)
                if memory and memory not in candidates:
                    if category is None or memory.category == category:
                        candidates.append(memory)

        seen = {id(m) for m in candidates}
        for memory in self._index.values():
            if id(memory) in seen:
                continue
            if category and memory.category != category:
                continue
            candidates.append(memory)

        candidates.sort(key=lambda m: (m.confidence, m.access_count), reverse=True)
        return candidates[:limit]

    def summarize(self, category: Optional[str] = None, max_chars: int = 800) -> str:
        """简单记忆摘要：按 confidence 取 top 条目拼成文本。"""
        memories = sorted(self._index.values(), key=lambda m: m.confidence, reverse=True)
        if category:
            memories = [m for m in memories if m.category == category]
        if not memories:
            return ""
        lines = ["## 记忆摘要"]
        current_len = len(lines[0])
        for m in memories[:50]:
            text = f"- [{m.category}] {m.key}: {m.value}"
            if current_len + len(text) + 1 > max_chars:
                break
            lines.append(text)
            current_len += len(text) + 1
        return "\n".join(lines)

    def list_by_category(self, category: str) -> List[Memory]:
        return [m for m in self._index.values() if m.category == category]

    def get_context(self, max_items: int = 5) -> str:
        memories = sorted(self._index.values(), key=lambda m: m.confidence, reverse=True)[:max_items]
        if not memories:
            return ""
        lines = ["## 记忆上下文"]
        for m in memories:
            lines.append(f"- [{m.category}] {m.key}: {m.value[:100]}")
        return "\n".join(lines)

    def clear(self) -> None:
        self._index.clear()
        self._embedding_index.clear()
        self._save()


# 全局记忆实例
memory = PersistentMemory()
persistent_memory = memory
