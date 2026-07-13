"""
PRISM Agent - 分布式锁
多进程/多机器资源锁，防并发冲突
"""

from __future__ import annotations

import json
import logging
import os
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)

_LOCK_DIR = Path.home() / ".prism" / "locks"
_LOCK_DIR.mkdir(parents=True, exist_ok=True)


@dataclass
class Lock:
    name: str
    owner: str = ""
    ttl: int = 60
    created_at: float = field(default_factory=time.time)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "name": self.name,
            "owner": self.owner,
            "ttl": self.ttl,
            "created_at": self.created_at,
        }


class DistributedLock:
    def __init__(self) -> None:
        self._held: Dict[str, Lock] = {}

    def acquire(self, name: str, owner: str = "", ttl: int = 60) -> bool:
        lock_file = _LOCK_DIR / f"{name}.lock"
        if lock_file.exists():
            try:
                data = json.loads(lock_file.read_text(encoding="utf-8"))
                if time.time() - data.get("created_at", 0) < data.get("ttl", 0):
                    return False
            except Exception:
                pass
        lock = Lock(name=name, owner=owner, ttl=ttl)
        try:
            lock_file.write_text(json.dumps(lock.to_dict(), ensure_ascii=False), encoding="utf-8")
            self._held[name] = lock
            return True
        except Exception:
            return False

    def release(self, name: str) -> bool:
        lock_file = _LOCK_DIR / f"{name}.lock"
        try:
            lock_file.unlink()
        except Exception:
            pass
        return self._held.pop(name, None) is not None

    def is_locked(self, name: str) -> bool:
        lock_file = _LOCK_DIR / f"{name}.lock"
        if not lock_file.exists():
            return False
        try:
            data = json.loads(lock_file.read_text(encoding="utf-8"))
            if time.time() - data.get("created_at", 0) >= data.get("ttl", 0):
                lock_file.unlink()
                return False
        except Exception:
            pass
        return True


distributed_lock = DistributedLock()
