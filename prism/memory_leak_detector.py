"""
PRISM Agent - 内存泄漏检测
监控长时间运行的进程内存
"""

from __future__ import annotations

import json
import logging
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)

_LEAK_DIR = Path.home() / ".prism" / "leak"
_LEAK_DIR.mkdir(parents=True, exist_ok=True)


@dataclass
class MemorySample:
    ts: float = field(default_factory=time.time)
    rss_mb: float = 0.0
    vms_mb: float = 0.0

    def to_dict(self) -> Dict[str, Any]:
        return {
            "ts": self.ts,
            "rss_mb": round(self.rss_mb, 1),
            "vms_mb": round(self.vms_mb, 1),
        }


class MemoryLeakDetector:
    def __init__(self, pid: Optional[int] = None) -> None:
        self.pid = pid
        self._samples: List[MemorySample] = []
        self._psutil = None
        try:
            import psutil
            self._psutil = psutil
        except Exception:
            pass

    def sample(self) -> MemorySample:
        sample = MemorySample()
        if self._psutil and self.pid:
            try:
                proc = self._psutil.Process(self.pid)
                mem = proc.memory_info()
                sample.rss_mb = mem.rss / 1024 / 1024
                sample.vms_mb = mem.vms / 1024 / 1024
            except Exception:
                pass
        elif self._psutil:
            try:
                proc = self._psutil.Process()
                mem = proc.memory_info()
                sample.rss_mb = mem.rss / 1024 / 1024
                sample.vms_mb = mem.vms / 1024 / 1024
            except Exception:
                pass
        self._samples.append(sample)
        return sample

    def detect_leak(self, window: int = 20, threshold_mb: float = 50.0) -> bool:
        if len(self._samples) < window:
            return False
        recent = [s.rss_mb for s in self._samples[-window:]]
        if recent[-1] - recent[0] > threshold_mb:
            logger.warning("possible memory leak: +%.1f MB", recent[-1] - recent[0])
            return True
        return False

    def samples(self) -> List[Dict[str, Any]]:
        return [s.to_dict() for s in self._samples]


memory_leak_detector = MemoryLeakDetector()
