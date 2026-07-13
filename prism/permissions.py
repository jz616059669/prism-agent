"""
PRISM Agent - 细粒度权限沙盒
控制文件 / 终端 / 网络三类操作的会话级开关
"""

from __future__ import annotations

import json
import logging
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)

_PERM_FILE = Path.home() / ".prism" / "permissions.json"


@dataclass
class PermissionPolicy:
    allow_file_write: bool = False
    allow_terminal: bool = True
    allow_network: bool = True
    allow_browser: bool = True
    read_only_paths: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "allow_file_write": self.allow_file_write,
            "allow_terminal": self.allow_terminal,
            "allow_network": self.allow_network,
            "allow_browser": self.allow_browser,
            "read_only_paths": list(self.read_only_paths),
        }


class PermissionStore:
    def __init__(self) -> None:
        self._policy = PermissionPolicy()
        self._load()

    def _load(self) -> None:
        if not _PERM_FILE.exists():
            return
        try:
            data = json.loads(_PERM_FILE.read_text(encoding="utf-8"))
            self._policy = PermissionPolicy(**{k: v for k, v in data.items() if k in PermissionPolicy().__dict__})
        except Exception:
            pass

    def save(self) -> None:
        try:
            _PERM_FILE.write_text(json.dumps(self._policy.to_dict(), ensure_ascii=False, indent=2), encoding="utf-8")
        except Exception:
            pass

    @property
    def policy(self) -> PermissionPolicy:
        return self._policy

    def update(self, **kwargs) -> PermissionPolicy:
        for key, value in kwargs.items():
            if hasattr(self._policy, key):
                setattr(self._policy, key, value)
        self.save()
        return self._policy


permission_store = PermissionStore()
