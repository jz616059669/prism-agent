"""
PRISM Agent - Response Cache
LLM 响应缓存，相同 prompt 不重复请求，省钱提速
"""

from __future__ import annotations

import hashlib
import json
import logging
import os
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, Optional

logger = logging.getLogger(__name__)

_CACHE_DIR = Path.home() / ".prism" / "cache"
_CACHE_DIR.mkdir(parents=True, exist_ok=True)


@dataclass
class CachedResponse:
    key: str
    response: str = ""
    model: str = ""
    created_at: float = field(default_factory=time.time)
    hits: int = 0

    def to_dict(self) -> Dict[str, Any]:
        return {
            "key": self.key,
            "response": self.response,
            "model": self.model,
            "created_at": self.created_at,
            "hits": self.hits,
        }


class ResponseCache:
    def __init__(self, ttl: int = 3600) -> None:
        self.ttl = ttl
        self._hits = 0
        self._misses = 0

    def _hash(self, prompt: str, model: str) -> str:
        payload = f"{model}:{prompt}"
        return hashlib.sha256(payload.encode("utf-8")).hexdigest()[:32]

    def get(self, prompt: str, model: str = "") -> Optional[CachedResponse]:
        key = self._hash(prompt, model)
        path = _CACHE_DIR / f"{key}.json"
        if not path.exists():
            self._misses += 1
            return None
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
            if time.time() - data.get("created_at", 0) > self.ttl:
                path.unlink()
                self._misses += 1
                return None
            data["hits"] = data.get("hits", 0) + 1
            path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
            self._hits += 1
            return CachedResponse(**data)
        except Exception:
            self._misses += 1
            return None

    def put(self, prompt: str, response: str, model: str = "") -> CachedResponse:
        key = self._hash(prompt, model)
        cached = CachedResponse(key=key, response=response, model=model)
        try:
            (_CACHE_DIR / f"{key}.json").write_text(json.dumps(cached.to_dict(), ensure_ascii=False, indent=2), encoding="utf-8")
        except Exception:
            pass
        return cached

    def stats(self) -> Dict[str, Any]:
        return {"hits": self._hits, "misses": self._misses, "ttl": self.ttl}


response_cache = ResponseCache()
