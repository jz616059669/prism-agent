"""
PRISM Agent - Chaos Testing 混沌测试
随机注入失败，验证自修复/降级/重试是否生效
"""

from __future__ import annotations

import logging
import random
import time
from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List, Optional

logger = logging.getLogger(__name__)


@dataclass
class ChaosResult:
    scenario: str
    injected: bool = False
    recovered: bool = False
    latency_ms: float = 0.0
    error: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return {
            "scenario": self.scenario,
            "injected": self.injected,
            "recovered": self.recovered,
            "latency_ms": self.latency_ms,
            "error": self.error,
        }


class ChaosTester:
    def __init__(self, seed: Optional[int] = None) -> None:
        self._rng = random.Random(seed)
        self._history: List[ChaosResult] = []

    def run(self, scenarios: List[str], fn: Callable[[str], Any]) -> List[ChaosResult]:
        results: List[ChaosResult] = []
        for scenario in scenarios:
            result = ChaosResult(scenario=scenario)
            start = time.time()
            try:
                if self._should_inject():
                    result.injected = True
                    raise RuntimeError(f"chaos:{scenario}")
                fn(scenario)
                result.recovered = True
            except Exception as exc:
                result.error = str(exc)
                if self._is_chaos_error(exc):
                    result.injected = True
                elif "chaos:" not in str(exc):
                    raise
            result.latency_ms = (time.time() - start) * 1000.0
            self._history.append(result)
        return results

    def history(self, limit: int = 50) -> List[Dict[str, Any]]:
        return [r.to_dict() for r in self._history[-limit:]]

    def _should_inject(self) -> bool:
        return self._rng.random() < 0.3

    def _is_chaos_error(self, exc: Exception) -> bool:
        text = str(exc).lower()
        return text.startswith("chaos:") or "chaos" in text


chaos_tester = ChaosTester()
