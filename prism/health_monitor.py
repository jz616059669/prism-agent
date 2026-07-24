"""
PRISM Agent - 健康检查/心跳
进程存活检测 + 自动重启
"""

from __future__ import annotations

import json
import logging
import os
import subprocess
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)

_HEALTH_DIR = Path.home() / ".prism" / "health"
_HEALTH_DIR.mkdir(parents=True, exist_ok=True)


@dataclass
class HealthCheck:
    name: str
    status: str = "unknown"
    last_check: float = 0.0
    restart_count: int = 0
    last_error: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return {
            "name": self.name,
            "status": self.status,
            "last_check": self.last_check,
            "restart_count": self.restart_count,
            "last_error": self.last_error,
        }


class HealthMonitor:
    def __init__(self) -> None:
        self._checks: Dict[str, HealthCheck] = {}
        self._load()

    def _load(self) -> None:
        state_file = _HEALTH_DIR / "state.json"
        if not state_file.exists():
            return
        try:
            data = json.loads(state_file.read_text(encoding="utf-8"))
            for item in data:
                hc = HealthCheck(**item)
                self._checks[hc.name] = hc
        except Exception:
            pass

    def register(self, name: str, cmd: str = "") -> HealthCheck:
        hc = self._checks.get(name) or HealthCheck(name=name)
        hc.last_check = time.time()
        hc.status = "running"
        self._checks[name] = hc
        self._save()
        return hc

    def heartbeat(self, name: str) -> HealthCheck:
        hc = self._checks.get(name) or HealthCheck(name=name)
        hc.last_check = time.time()
        if hc.status != "running":
            hc.status = "running"
        self._save()
        return hc

    def mark_failed(self, name: str, error: str = "") -> HealthCheck:
        hc = self._checks.get(name) or HealthCheck(name=name)
        hc.last_check = time.time()
        hc.status = "failed"
        hc.last_error = error
        self._save()
        return hc

    def restart(self, name: str, cmd: str = "") -> HealthCheck:
        hc = self._checks.get(name) or HealthCheck(name=name)
        hc.restart_count += 1
        hc.last_check = time.time()
        hc.status = "running"
        hc.last_error = ""
        self._save()
        if cmd:
            try:
                import shlex
                parts = shlex.split(cmd)
                if parts:
                    subprocess.Popen(parts, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            except Exception:
                pass
        return hc

    def list_checks(self) -> List[Dict[str, Any]]:
        return [hc.to_dict() for hc in self._checks.values()]

    def _save(self) -> None:
        try:
            (_HEALTH_DIR / "state.json").write_text(
                json.dumps([hc.to_dict() for hc in self._checks.values()], ensure_ascii=False, indent=2),
                encoding="utf-8",
            )
        except Exception:
            pass


health_monitor = HealthMonitor()
