"""
PRISM Agent - Rate Limiter 内置
防止 API 超限，自动 backoff
"""

from __future__ import annotations

import logging
import threading
import time
from dataclasses import dataclass, field
from typing import Dict, Optional

logger = logging.getLogger(__name__)


@dataclass
class RateLimitResult:
    allowed: bool
    retry_after: float = 0.0
    remaining: int = 0
    reset: float = 0.0


class RateLimiter:
    _instance: Optional["RateLimiter"] = None

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._buckets: Dict[str, Dict[str, float]] = {}

    @classmethod
    def get_instance(cls) -> "RateLimiter":
        if cls._instance is None:
            cls._instance = RateLimiter()
        return cls._instance

    def check(self, key: str, limit: int = 60, window: int = 60) -> RateLimitResult:
        """滑动窗口限流。limit=每分钟最大请求数。"""
        now = time.time()
        with self._lock:
            bucket = self._buckets.get(key, {"timestamps": [], "reset": now + window})
            # 清理过期时间戳
            window_start = now - window
            bucket["timestamps"] = [t for t in bucket.get("timestamps", []) if t > window_start]
            bucket["reset"] = now + window
            remaining = max(0, limit - len(bucket["timestamps"]))
            allowed = remaining > 0
            if allowed:
                bucket["timestamps"].append(now)
            self._buckets[key] = bucket
            retry_after = 0.0
            if not allowed and bucket["timestamps"]:
                retry_after = bucket["timestamps"][0] + window - now
            return RateLimitResult(allowed=allowed, retry_after=retry_after, remaining=remaining, reset=bucket["reset"])

    def backoff(self, key: str, retry_after: float) -> None:
        try:
            time.sleep(max(0.0, min(retry_after, 60.0)))
        except Exception:
            pass


rate_limiter = RateLimiter.get_instance()
