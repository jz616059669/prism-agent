"""
PRISM Agent - 性能基准测试
自动跑 benchmark，记录历史，防回归
"""

from __future__ import annotations

import json
import logging
import statistics
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional

logger = logging.getLogger(__name__)

_BENCH_DIR = Path.home() / ".prism" / "benchmarks"
_BENCH_DIR.mkdir(parents=True, exist_ok=True)


@dataclass
class BenchmarkResult:
    name: str
    duration_ms: float = 0.0
    success: bool = True
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "name": self.name,
            "duration_ms": self.duration_ms,
            "success": self.success,
            "metadata": self.metadata,
        }


class BenchmarkStore:
    def __init__(self, max_history: int = 200) -> None:
        self._history: List[BenchmarkResult] = []
        self._max_history = max_history
        self._load()

    def _load(self) -> None:
        history_file = _BENCH_DIR / "history.jsonl"
        if not history_file.exists():
            return
        try:
            for line in history_file.read_text(encoding="utf-8").splitlines():
                if not line.strip():
                    continue
                try:
                    data = json.loads(line)
                    self._history.append(BenchmarkResult(**data))
                except Exception:
                    continue
        except Exception:
            pass

    def record(self, result: BenchmarkResult) -> None:
        self._history.append(result)
        if len(self._history) > self._max_history:
            self._history = self._history[-self._max_history:]
        try:
            with (_BENCH_DIR / "history.jsonl").open("a", encoding="utf-8") as f:
                f.write(json.dumps(result.to_dict(), ensure_ascii=False) + "\n")
        except Exception:
            pass

    def summary(self, name: str) -> Dict[str, Any]:
        items = [r.duration_ms for r in self._history if r.name == name and r.success]
        if not items:
            return {"name": name, "count": 0}
        return {
            "name": name,
            "count": len(items),
            "avg_ms": round(statistics.mean(items), 2),
            "p95_ms": round(sorted(items)[int(len(items) * 0.95)], 2),
            "min_ms": round(min(items), 2),
            "max_ms": round(max(items), 2),
        }


benchmark_store = BenchmarkStore()


class Benchmark:
    def __init__(self, name: str) -> None:
        self.name = name
        self._start = 0.0

    def __enter__(self):
        self._start = time.perf_counter()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        duration_ms = (time.perf_counter() - self._start) * 1000.0
        benchmark_store.record(BenchmarkResult(name=self.name, duration_ms=duration_ms, success=exc_type is None))
        return False


def benchmark(fn: Callable[..., Any]) -> Callable[..., Any]:
    import functools
    name = getattr(fn, "__name__", "benchmark")

    @functools.wraps(fn)
    def wrapper(*args: Any, **kwargs: Any):
        with Benchmark(name=name):
            return fn(*args, **kwargs)

    return wrapper
