"""PRISM Agent - 统一抽象接口层

将 tools / memory / gateway 的核心协议抽成独立接口，
方便外部复用、测试替换、以及未来外化为 prism-sdk。
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Callable
from datetime import datetime
from abc import ABC, abstractmethod


__all__ = [
    "Message",
    "PlatformAdapter",
    "Tool",
    "MemoryProvider",
    "MemoryRecord",
    "ToolRegistry",
    "MemoryProviderRegistry",
    "GatewayRegistry",
]


# ---------------------------------------------------------------------------
# Gateway 接口
# ---------------------------------------------------------------------------
@dataclass
class Message:
    platform: str
    chat_id: str
    user_id: str
    text: str
    raw: Optional[Dict[str, Any]] = None
    timestamp: datetime = field(default_factory=datetime.now)
    message_type: str = "text"
    media_url: Optional[str] = None
    file_id: Optional[str] = None


class PlatformAdapter(ABC):
    @abstractmethod
    def send(self, chat_id: str, text: str) -> bool:
        pass

    @abstractmethod
    def start_polling(self, handler: Callable[[Message], None]) -> None:
        pass

    @abstractmethod
    def stop(self) -> None:
        pass


# ---------------------------------------------------------------------------
# Tool 接口
# ---------------------------------------------------------------------------
class Tool(ABC):
    @property
    @abstractmethod
    def name(self) -> str:
        pass

    @property
    @abstractmethod
    def description(self) -> str:
        pass

    @property
    def input_schema(self) -> Optional[Dict[str, Any]]:
        return None

    @abstractmethod
    def execute(self, **kwargs: Any) -> Dict[str, Any]:
        pass


# ---------------------------------------------------------------------------
# Memory 接口
# ---------------------------------------------------------------------------
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
    name: str = "base"

    @abstractmethod
    def init(self) -> None:
        pass

    @abstractmethod
    def add(self, record: MemoryRecord) -> None:
        pass

    @abstractmethod
    def get(self, key: str) -> Optional[MemoryRecord]:
        pass

    @abstractmethod
    def delete(self, key: str) -> None:
        pass

    @abstractmethod
    def list_keys(self) -> List[str]:
        pass

    @abstractmethod
    def search(self, query: str, top_k: int = 5) -> List[tuple]:
        pass

    @abstractmethod
    def clear(self) -> None:
        pass


# ---------------------------------------------------------------------------
# Registry 接口
# ---------------------------------------------------------------------------
class ToolRegistry:
    def __init__(self) -> None:
        self._tools: Dict[str, Tool] = {}

    def register(self, tool: Tool) -> None:
        self._tools[tool.name] = tool

    def get(self, name: str) -> Optional[Tool]:
        return self._tools.get(name)

    def list_tools(self) -> List[Dict[str, Any]]:
        return [
            {
                "name": t.name,
                "description": t.description,
                "inputSchema": t.input_schema or {"type": "object", "properties": {}},
            }
            for t in self._tools.values()
        ]

    def execute(self, name: str, **kwargs: Any) -> Dict[str, Any]:
        tool = self._tools.get(name)
        if not tool:
            return {"success": False, "error": f"Tool not found: {name}"}
        try:
            return tool.execute(**kwargs)
        except Exception as exc:
            return {"success": False, "error": str(exc)}


class MemoryProviderRegistry:
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


class GatewayRegistry:
    def __init__(self) -> None:
        self._gateway: Optional[object] = None

    @property
    def gateway(self) -> object:
        if self._gateway is None:
            from prism.gateway import gateway as _gw
            self._gateway = _gw
        return self._gateway

    def register(self, name: str, adapter: PlatformAdapter) -> None:
        self.gateway.adapters[name] = adapter
        self.gateway._platforms = list(self.gateway.adapters.keys())

    def get(self, name: str) -> Optional[PlatformAdapter]:
        return self.gateway.adapters.get(name)

    @property
    def names(self) -> List[str]:
        return list(self.gateway.adapters.keys())
