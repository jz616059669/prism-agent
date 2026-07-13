"""
PRISM Agent - 性能 profiling 内置
自动降级：延迟高/连续失败时降低模型档次或跳过工具
"""

from __future__ import annotations

import logging
import threading
import time
from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List, Optional

logger = logging.getLogger(__name__)


@dataclass
class ProfileRecord:
    ts: float
    model: str
    latency_ms: float
    prompt_tokens: int = 0
    completion_tokens: int = 0
    success: bool = True
    degraded: bool = False


class Profiler:
    _instance: Optional["Profiler"] = None

    def __init__(self) -> None:
        self._records: List[ProfileRecord] = []
        self._lock = threading.Lock()
        self._degraded_until: float = 0.0
        self._degraded_model: Optional[str] = None
        self._fail_count: int = 0

    @classmethod
    def get_instance(cls) -> "Profiler":
        if cls._instance is None:
            cls._instance = Profiler()
        return cls._instance

    def record(self, model: str, latency_ms: float = 0.0, prompt_tokens: int = 0, completion_tokens: int = 0, success: bool = True) -> None:
        with self._lock:
            rec = ProfileRecord(
                ts=time.time(),
                model=model,
                latency_ms=max(0.0, latency_ms),
                prompt_tokens=max(0, prompt_tokens),
                completion_tokens=max(0, completion_tokens),
                success=success,
                degraded=self._is_degraded_now(),
            )
            self._records.append(rec)
            if len(self._records) > 2000:
                self._records = self._records[-1000:]
            self._update_degradation(rec)

    def _update_degradation(self, rec: ProfileRecord) -> None:
        now = time.time()
        if now > self._degraded_until:
            self._degraded_until = 0.0
            self._degraded_model = None
            self._fail_count = 0
        if not rec.success:
            self._fail_count += 1
        else:
            self._fail_count = max(0, self._fail_count - 1)
        recent = [r for r in self._records[-20:] if time.time() - r.ts < 600]
        if not recent:
            return
        fail_rate = sum(1 for r in recent if not r.success) / len(recent)
        avg_latency = sum(r.latency_ms for r in recent) / len(recent)
        if self._fail_count >= 5 or fail_rate >= 0.5 or avg_latency > 8000:
            self._degraded_until = now + 120
            self._degraded_model = rec.model

    def _is_degraded_now(self) -> bool:
        return time.time() < self._degraded_until

    @property
    def is_degraded(self) -> bool:
        return self._is_degraded_now()

    @property
    def degraded_model(self) -> Optional[str]:
        if self._is_degraded_now():
            return self._degraded_model
        return None

    def stats(self) -> Dict[str, Any]:
        with self._lock:
            records = list(self._records)
        if not records:
            return {"total": 0, "avg_latency_ms": 0.0, "fail_rate": 0.0, "degraded": False}
        total = len(records)
        avg_latency = sum(r.latency_ms for r in records) / total
        fail_rate = sum(1 for r in records if not r.success) / total
        return {
            "total": total,
            "avg_latency_ms": round(avg_latency, 1),
            "fail_rate": round(fail_rate * 100, 1),
            "degraded": self._is_degraded_now(),
            "degraded_model": self._degraded_model,
        }


profiler = Profiler.get_instance()
