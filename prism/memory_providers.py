"""
PRISM Agent - Memory Providers 插件化接口
提供统一抽象 + 本地默认实现，外部后端可按此接口替换。
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional


@dataclass
class MemoryRecord:
    key: str
    value: str
    category: str = "general"
    confidence: float = 1.0
    source: str = "user"
    created_at: str = ""
    updated_at: str = ""
    meta: Dict[str, Any] = field(default_factory=dict)


class MemoryProvider(ABC):
    """记忆后端抽象"""

    @abstractmethod
    def remember(self, record: MemoryRecord) -> bool:
        """写入/更新一条记忆"""
        raise NotImplementedError

    @abstractmethod
    def forget(self, key: str) -> bool:
        """删除一条记忆"""
        raise NotImplementedError

    @abstractmethod
    def recall(self, key: str) -> Optional[MemoryRecord]:
        """按 key 精确召回"""
        raise NotImplementedError

    @abstractmethod
    def search(self, query: str, category: Optional[str] = None, limit: int = 20) -> List[MemoryRecord]:
        """按 query/category 做检索召回"""
        raise NotImplementedError

    @abstractmethod
    def list_keys(self, category: Optional[str] = None) -> List[str]:
        """列出所有 key，可按 category 过滤"""
        raise NotImplementedError

    def health(self) -> Dict[str, Any]:
        return {"provider": self.__class__.__name__, "status": "unknown"}


class LocalMemoryProvider(MemoryProvider):
    """默认本地记忆实现，基于 prism.memory.persistent_memory"""

    def __init__(self) -> None:
        try:
            from prism.memory import persistent_memory
            self._impl = persistent_memory
        except Exception:
            self._impl = None  # type: ignore[assignment]

    def remember(self, record: MemoryRecord) -> bool:
        if self._impl is None:
            return False
        try:
            self._impl.remember(record.key, record.value, category=record.category)
            return True
        except Exception:
            return False

    def forget(self, key: str) -> bool:
        if self._impl is None:
            return False
        try:
            # prism.memory 无直接 forget，这里做标记删除
            self._impl.remember(key, "[已删除]", category="__deleted__")
            return True
        except Exception:
            return False

    def recall(self, key: str) -> Optional[MemoryRecord]:
        if self._impl is None:
            return None
        try:
            row = self._impl._index.get(key)
            if not row:
                return None
            return MemoryRecord(
                key=row.key,
                value=row.value,
                category=row.category,
                confidence=row.confidence,
                source=row.source,
                created_at=row.created_at,
                updated_at=row.updated_at,
            )
        except Exception:
            return None

    def search(self, query: str, category: Optional[str] = None, limit: int = 20) -> List[MemoryRecord]:
        if self._impl is None:
            return []
        try:
            hits = self._impl.search(query, category=category, limit=limit)
            out: List[MemoryRecord] = []
            for m in hits:
                out.append(MemoryRecord(
                    key=m.key,
                    value=m.value,
                    category=m.category,
                    confidence=m.confidence,
                    source=m.source,
                    created_at=getattr(m, "created_at", ""),
                    updated_at=getattr(m, "updated_at", ""),
                ))
            return out
        except Exception:
            return []

    def list_keys(self, category: Optional[str] = None) -> List[str]:
        if self._impl is None:
            return []
        try:
            return [k for k, m in self._impl._index.items() if category is None or m.category == category]
        except Exception:
            return []


class MemoryProviderRegistry:
    """记忆后端注册表，默认挂载 local"""

    def __init__(self) -> None:
        self._providers: Dict[str, MemoryProvider] = {"local": LocalMemoryProvider()}
        self._default = "local"

    def register(self, name: str, provider: MemoryProvider) -> None:
        self._providers[name] = provider

    def get(self, name: Optional[str] = None) -> MemoryProvider:
        return self._providers.get(name or self._default, self._providers[self._default])

    def set_default(self, name: str) -> None:
        if name in self._providers:
            self._default = name

    def names(self) -> List[str]:
        return list(self._providers.keys())


memory_provider_registry = MemoryProviderRegistry()


__all__ = [
    "MemoryRecord",
    "MemoryProvider",
    "LocalMemoryProvider",
    "MemoryProviderRegistry",
    "memory_provider_registry",
]
