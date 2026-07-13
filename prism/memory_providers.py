"""
PRISM Agent - Memory Providers
可插拔记忆后端：本地 JSON、Chroma、Qdrant、FAISS 文件向量
"""

from __future__ import annotations

import json
import logging
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

logger = logging.getLogger("prism.memory_providers")


@dataclass
class MemoryRecord:
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
    digest: str = ""


class MemoryProvider(ABC):
    """记忆后端基类"""

    name: str = "base"

    @abstractmethod
    def init(self) -> None:
        """初始化存储"""

    @abstractmethod
    def add(self, record: MemoryRecord) -> None:
        """写入单条记忆"""

    @abstractmethod
    def get(self, key: str) -> Optional[MemoryRecord]:
        """按 key 读取"""

    @abstractmethod
    def delete(self, key: str) -> None:
        """删除记忆"""

    @abstractmethod
    def list_keys(self) -> List[str]:
        """列出全部 key"""

    @abstractmethod
    def search(self, query: str, top_k: int = 5) -> List[Tuple[str, float]]:
        """语义检索，返回 (key, score)"""

    @abstractmethod
    def clear(self) -> None:
        """清空所有记忆"""


class MemoryProviderRegistry:
    """记忆提供者注册表，默认只装本地 JSON，其余按可选依赖注册。"""

    def __init__(self) -> None:
        self._providers: Dict[str, MemoryProvider] = {}
        self._default: Optional[str] = None

    def register(self, provider: MemoryProvider, default: bool = False) -> None:
        self._providers[provider.name] = provider
        if default or self._default is None:
            self._default = provider.name

    def get(self, name: Optional[str] = None) -> MemoryProvider:
        if not name:
            name = self._default
        if name not in self._providers:
            raise KeyError(f"memory provider not found: {name}")
        return self._providers[name]

    @property
    def names(self) -> List[str]:
        return list(self._providers.keys())


memory_provider_registry = MemoryProviderRegistry()


class LocalMemoryProvider(MemoryProvider):
    """默认本地 JSON 文件记忆，零外部依赖。"""

    name = "local"

    def __init__(self, base_dir: Optional[Path] = None) -> None:
        self.base_dir = Path(base_dir) if base_dir is not None else Path.home() / ".prism" / "memory"
        self.base_dir.mkdir(parents=True, exist_ok=True)
        self._index_path = self.base_dir / "index.json"
        self._index: Dict[str, MemoryRecord] = {}

    def init(self) -> None:
        self._load()

    def _load(self) -> None:
        if not self._index_path.exists():
            return
        try:
            data = json.loads(self._index_path.read_text(encoding="utf-8"))
            for item in data.get("memories", []):
                rec = MemoryRecord(
                    key=item["key"],
                    value=item["value"],
                    category=item.get("category", "general"),
                    confidence=float(item.get("confidence", 1.0)),
                    source=item.get("source", "user"),
                    created_at=item.get("created_at", ""),
                    updated_at=item.get("updated_at", ""),
                    embedding=item.get("embedding"),
                    embedding_model=item.get("embedding_model", ""),
                    access_count=int(item.get("access_count", 0)),
                    last_accessed_at=item.get("last_accessed_at", ""),
                    digest=item.get("digest", ""),
                )
                self._index[rec.key] = rec
        except Exception as exc:
            logger.warning("load local memory failed: %s", exc)
            self._index = {}

    def _save(self) -> None:
        try:
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
                        "digest": m.digest,
                    }
                    for m in self._index.values()
                ]
            }
            self._index_path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
        except Exception as exc:
            logger.warning("save local memory failed: %s", exc)

    def add(self, record: MemoryRecord) -> None:
        if record.key in self._index:
            existing = self._index[record.key]
            record.created_at = existing.created_at or record.created_at
            record.access_count = existing.access_count + 1
            record.last_accessed_at = record.created_at
        self._index[record.key] = record
        self._save()

    def get(self, key: str) -> Optional[MemoryRecord]:
        return self._index.get(key)

    def delete(self, key: str) -> None:
        self._index.pop(key, None)
        self._save()

    def list_keys(self) -> List[str]:
        return list(self._index.keys())

    def clear(self) -> None:
        self._index.clear()
        self._save()

    def search(self, query: str, top_k: int = 5) -> List[Tuple[str, float]]:
        if not self._index:
            return []
        query_lower = query.lower()
        scored: List[Tuple[str, float]] = []
        for key, rec in self._index.items():
            text = f"{key} {rec.value}".lower()
            score = 0.0
            for token in query_lower.split():
                if token and token in text:
                    score += 1.0
            if score > 0:
                scored.append((key, score))
        scored.sort(key=lambda x: x[1], reverse=True)
        return scored[:top_k]


class ChromaMemoryProvider(MemoryProvider):
    """可选 Chroma 向量记忆。需要 `pip install chromadb`。"""

    name = "chroma"

    def __init__(self, base_dir: Optional[Path] = None, collection: str = "prism_memory") -> None:
        self.base_dir = Path(base_dir) if base_dir is not None else Path.home() / ".prism" / "memory_chroma"
        self.collection_name = collection
        self._client = None
        self._collection = None

    def init(self) -> None:
        try:
            import chromadb  # type: ignore[import-untyped]
            from chromadb.config import Settings  # type: ignore[import-untyped]
        except ImportError as exc:
            raise RuntimeError("chromadb not installed. Run `pip install chromadb`.") from exc
        self._client = chromadb.Client(Settings(chroma_db_impl="duckdb+parquet", persist_directory=str(self.base_dir)))
        self._collection = self._client.get_or_create_collection(self.collection_name, metadata={"hnsw:space": "cosine"})

    def add(self, record: MemoryRecord) -> None:
        if self._collection is None:
            self.init()
        self._collection.add(
            documents=[record.value],
            metadatas=[{"key": record.key, "category": record.category, "source": record.source}],
            ids=[record.key],
        )

    def get(self, key: str) -> Optional[MemoryRecord]:
        if self._collection is None:
            self.init()
        result = self._collection.get(ids=[key])
        if not result["ids"]:
            return None
        meta = result["metadatas"][0] or {}
        return MemoryRecord(key=key, value=result["documents"][0], category=meta.get("category", "general"), source=meta.get("source", "user"))

    def delete(self, key: str) -> None:
        if self._collection is None:
            self.init()
        self._collection.delete(ids=[key])

    def list_keys(self) -> List[str]:
        if self._collection is None:
            self.init()
        return self._collection.get()["ids"]

    def search(self, query: str, top_k: int = 5) -> List[Tuple[str, float]]:
        if self._collection is None:
            self.init()
        result = self._collection.query(query_texts=[query], n_results=top_k)
        ids = result.get("ids", [[]])[0]
        distances = result.get("distances", [[]])[0]
        return [(str(i), 1.0 - float(d)) for i, d in zip(ids, distances)]

    def clear(self) -> None:
        if self._collection is None:
            self.init()
        self._collection.delete(where={})


class QdrantMemoryProvider(MemoryProvider):
    """可选 Qdrant 向量记忆。需要 `pip install qdrant-client`。"""

    name = "qdrant"

    def __init__(self, base_dir: Optional[Path] = None, collection: str = "prism_memory", url: str = "http://localhost:6333") -> None:
        self.base_dir = Path(base_dir) if base_dir is not None else Path.home() / ".prism" / "memory_qdrant"
        self.collection = collection
        self.url = url
        self._client = None

    def init(self) -> None:
        try:
            from qdrant_client import QdrantClient  # type: ignore[import-untyped]
            from qdrant_client.http import models  # type: ignore[import-untyped]
        except ImportError as exc:
            raise RuntimeError("qdrant-client not installed. Run `pip install qdrant-client`.") from exc
        self._client = QdrantClient(url=self.url)
        self._client.recreate_collection(
            collection_name=self.collection,
            vectors_config=models.VectorParams(size=384, distance=models.Distance.COSINE),
        )
        self._models = models

    def add(self, record: MemoryRecord) -> None:
        if self._client is None:
            self.init()
        from qdrant_client.http import models  # type: ignore[import-untyped]
        self._client.upsert(
            collection_name=self.collection,
            points=[models.PointStruct(id=record.key, payload={"value": record.value, "category": record.category}, vector=[0.0] * 384)],
        )

    def get(self, key: str) -> Optional[MemoryRecord]:
        if self._client is None:
            self.init()
        result = self._client.retrieve(collection_name=self.collection, ids=[key])
        if not result:
            return None
        p = result[0].payload or {}
        return MemoryRecord(key=key, value=p.get("value", ""), category=p.get("category", "general"))

    def delete(self, key: str) -> None:
        if self._client is None:
            self.init()
        self._client.delete(collection_name=self.collection, points_selector=[key])

    def list_keys(self) -> List[str]:
        if self._client is None:
            self.init()
        points = self._client.scroll(collection_name=self.collection, with_payload=False, with_vectors=False)[0]
        return [str(p.id) for p in points]

    def search(self, query: str, top_k: int = 5) -> List[Tuple[str, float]]:
        return []

    def clear(self) -> None:
        if self._client is None:
            self.init()
        self._client.delete_collection(self.collection)
        self.init()


def autoregister(default_path: Optional[Path] = None) -> None:
    """自动注册可用 provider，本地 JSON 始终注册为默认。"""
    local = LocalMemoryProvider(base_dir=default_path)
    local.init()
    memory_provider_registry.register(local, default=True)

    try:
        memory_provider_registry.register(ChromaMemoryProvider(base_dir=default_path), default=False)
    except (ImportError, RuntimeError, Exception):
        pass

    try:
        memory_provider_registry.register(QdrantMemoryProvider(base_dir=default_path), default=False)
    except (ImportError, RuntimeError, Exception):
        pass
