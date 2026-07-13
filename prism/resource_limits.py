"""
PRISM Agent - Resource Limits 资源限制
内存/CPU/磁盘/网络/时间维度限制，防止 runaway
"""

from __future__ import annotations

import logging
import os
import time
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)

_resource_available = True
try:
    import resource as _resource_module
except Exception:
    _resource_available = False


@dataclass
class ResourceLimits:
    max_memory_mb: int = 512
    max_cpu_percent: float = 80.0
    max_disk_mb: int = 1024
    max_network_mb: int = 512
    max_runtime_seconds: int = 600

    def to_dict(self) -> Dict[str, Any]:
        return {
            "max_memory_mb": self.max_memory_mb,
            "max_cpu_percent": self.max_cpu_percent,
            "max_disk_mb": self.max_disk_mb,
            "max_network_mb": self.max_network_mb,
            "max_runtime_seconds": self.max_runtime_seconds,
        }


@dataclass
class ResourceUsage:
    memory_mb: float = 0.0
    cpu_percent: float = 0.0
    disk_mb: float = 0.0
    network_mb: float = 0.0
    runtime_seconds: float = 0.0

    def to_dict(self) -> Dict[str, Any]:
        return {
            "memory_mb": self.memory_mb,
            "cpu_percent": self.cpu_percent,
            "disk_mb": self.disk_mb,
            "network_mb": self.network_mb,
            "runtime_seconds": self.runtime_seconds,
        }


class ResourceLimiter:
    def __init__(self, limits: Optional[ResourceLimits] = None) -> None:
        self.limits = limits or ResourceLimits()
        self._start = time.time()

    def check(self) -> ResourceUsage:
        usage = ResourceUsage(
            memory_mb=self._get_memory_mb(),
            cpu_percent=self._get_cpu_percent(),
            disk_mb=self._get_disk_mb(),
            network_mb=self._get_network_mb(),
            runtime_seconds=time.time() - self._start,
        )
        violations = self._violations(usage)
        if violations:
            logger.warning("resource limits exceeded: %s", violations)
        return usage

    def _violations(self, usage: ResourceUsage) -> List[str]:
        violations = []
        if usage.memory_mb > self.limits.max_memory_mb:
            violations.append(f"memory={usage.memory_mb:.1f}MB > {self.limits.max_memory_mb}MB")
        if usage.cpu_percent > self.limits.max_cpu_percent:
            violations.append(f"cpu={usage.cpu_percent:.1f}% > {self.limits.max_cpu_percent}%")
        if usage.disk_mb > self.limits.max_disk_mb:
            violations.append(f"disk={usage.disk_mb:.1f}MB > {self.limits.max_disk_mb}MB")
        if usage.network_mb > self.limits.max_network_mb:
            violations.append(f"network={usage.network_mb:.1f}MB > {self.limits.max_network_mb}MB")
        if usage.runtime_seconds > self.limits.max_runtime_seconds:
            violations.append(f"runtime={usage.runtime_seconds:.1f}s > {self.limits.max_runtime_seconds}s")
        return violations

    def _get_memory_mb(self) -> float:
        if _resource_available:
            try:
                usage = _resource_module.getrusage(_resource_module.RUSAGE_SELF)
                if hasattr(usage, "ru_maxrss"):
                    return usage.ru_maxrss / 1024.0
            except Exception:
                pass
        return 0.0

    def _get_cpu_percent(self) -> float:
        if _resource_available:
            try:
                usage = _resource_module.getrusage(_resource_module.RUSAGE_SELF)
                utime = usage.ru_utime
                stime = usage.ru_stime
                total = utime + stime
                runtime = time.time() - self._start
                if runtime > 0:
                    return (total / runtime) * 100.0
            except Exception:
                pass
        return 0.0

    def _get_disk_mb(self) -> float:
        try:
            path = os.path.expanduser("~/.prism")
            if os.path.exists(path):
                total = 0
                for dirpath, dirnames, filenames in os.walk(path):
                    for f in filenames:
                        fp = os.path.join(dirpath, f)
                        if os.path.isfile(fp):
                            total += os.path.getsize(fp)
                return total / (1024.0 * 1024.0)
        except Exception:
            pass
        return 0.0

    def _get_network_mb(self) -> float:
        return 0.0


resource_limiter = ResourceLimiter()
