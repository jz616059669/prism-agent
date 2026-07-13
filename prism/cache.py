"""
PRISM Agent - Redis 缓存层
会话级/全局级缓存，无 Redis 时自动降级到内存
"""

from __future__ import annotations

import logging
import time
from typing import Any, Dict, Optional

logger = logging.getLogger(__name__)

try:
    import redis

    _REDIS_AVAILABLE = True
except Exception:
    _REDIS_AVAILABLE = False


class _MemoryCache:
    def __init__(self) -> None:
        self._store: Dict[str, Any] = {}
        self._expiry: Dict[str, float] = {}

    def get(self, key: str) -> Optional[Any]:
        if key in self._expiry and time.time() > self._expiry[key]:
            self.delete(key)
            return None
        return self._store.get(key)

    def set(self, key: str, value: Any, ttl: int = 60) -> None:
        self._store[key] = value
        if ttl > 0:
            self._expiry[key] = time.time() + ttl

    def delete(self, key: str) -> None:
        self._store.pop(key, None)
        self._expiry.pop(key, None)


class CacheLayer:
    def __init__(self, url: Optional[str] = None) -> None:
        self._url = url or os.environ.get("REDIS_URL")
        self._client = None
        if _REDIS_AVAILABLE and self._url:
            try:
                self._client = redis.Redis.from_url(self._url)
                self._client.ping()
            except Exception:
                self._client = None
        self._fallback = _MemoryCache()

    def get(self, key: str) -> Optional[Any]:
        if self._client:
            try:
                val = self._client.get(key)
                if val is not None:
                    return __import__("json").loads(val)
            except Exception:
                pass
        return self._fallback.get(key)

    def set(self, key: str, value: Any, ttl: int = 60) -> None:
        if self._client:
            try:
                self._client.setex(key, ttl, __import__("json").dumps(value, ensure_ascii=False))
                return
            except Exception:
                pass
        self._fallback.set(key, value, ttl=ttl)

    def delete(self, key: str) -> None:
        if self._client:
            try:
                self._client.delete(key)
            except Exception:
                pass
        self._fallback.delete(key)


import os

cache = CacheLayer()
