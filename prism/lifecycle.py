"""
PRISM Agent - 应用生命周期管理
启动/关闭/重启/健康检查 + 状态持久化
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

_LIFE_DIR = Path.home() / ".prism" / "lifecycle"
_LIFE_DIR.mkdir(parents=True, exist_ok=True)


@dataclass
class ServiceStatus:
    name: str
    pid: int = 0
    status: str = "stopped"
    uptime: float = 0.0
    restarts: int = 0
    last_error: str = ""
    started_at: float = 0.0

    def to_dict(self) -> Dict[str, Any]:
        return {
            "name": self.name,
            "pid": self.pid,
            "status": self.status,
            "uptime": self.uptime,
            "restarts": self.restarts,
            "last_error": self.last_error,
            "started_at": self.started_at,
        }


class LifecycleManager:
    def __init__(self) -> None:
        self._services: Dict[str, ServiceStatus] = {}
        self._processes: Dict[str, subprocess.Popen] = {}
        self._load()

    def _load(self) -> None:
        state_file = _LIFE_DIR / "services.json"
        if not state_file.exists():
            return
        try:
            data = json.loads(state_file.read_text(encoding="utf-8"))
            for item in data:
                svc = ServiceStatus(**item)
                self._services[svc.name] = svc
        except Exception:
            pass

    def _save(self) -> None:
        try:
            (_LIFE_DIR / "services.json").write_text(
                json.dumps([s.to_dict() for s in self._services.values()], ensure_ascii=False, indent=2),
                encoding="utf-8",
            )
        except Exception:
            pass

    def start(self, name: str, cmd: str) -> ServiceStatus:
        svc = self._services.get(name) or ServiceStatus(name=name)
        try:
            process = subprocess.Popen(cmd, shell=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            time.sleep(0.5)
            if process.poll() is None:
                svc.pid = process.pid
                svc.status = "running"
                svc.started_at = time.time()
                svc.last_error = ""
                self._processes[name] = process
            else:
                svc.status = "stopped"
                svc.last_error = "process exited immediately"
        except Exception as exc:
            svc.status = "stopped"
            svc.last_error = str(exc)
        self._services[name] = svc
        self._save()
        return svc

    def stop(self, name: str) -> ServiceStatus:
        svc = self._services.get(name) or ServiceStatus(name=name)
        process = self._processes.pop(name, None)
        if process and process.poll() is None:
            try:
                process.terminate()
                time.sleep(0.5)
                if process.poll() is None:
                    process.kill()
            except Exception:
                pass
        svc.status = "stopped"
        svc.pid = 0
        svc.uptime = 0.0
        self._save()
        return svc

    def restart(self, name: str, cmd: str) -> ServiceStatus:
        self.stop(name)
        svc = self._services.get(name) or ServiceStatus(name=name)
        svc.restarts += 1
        return self.start(name, cmd)

    def health(self, name: str) -> Dict[str, Any]:
        svc = self._services.get(name)
        if not svc:
            return {"status": "unknown"}
        process = self._processes.get(name)
        if process and process.poll() is None:
            svc.uptime = max(0.0, time.time() - svc.started_at)
            svc.status = "running"
        else:
            svc.status = "stopped"
            svc.uptime = 0.0
        self._save()
        return svc.to_dict()

    def list_services(self) -> List[Dict[str, Any]]:
        result = []
        for svc in self._services.values():
            result.append(self.health(svc.name))
        return result


lifecycle = LifecycleManager()
