"""
PRISM Agent - Feature Flags 动态开关
运行时启用/禁用功能，不重启生效
"""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)

_FLAGS_DIR = Path.home() / ".prism" / "feature_flags"
_FLAGS_DIR.mkdir(parents=True, exist_ok=True)


@dataclass
class FeatureFlag:
    key: str
    enabled: bool = False
    description: str = ""
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "key": self.key,
            "enabled": self.enabled,
            "description": self.description,
            "metadata": self.metadata,
        }


class FeatureFlags:
    def __init__(self) -> None:
        self._flags: Dict[str, FeatureFlag] = {}
        self._load()

    def _load(self) -> None:
        flags_file = _FLAGS_DIR / "flags.json"
        if not flags_file.exists():
            return
        try:
            data = json.loads(flags_file.read_text(encoding="utf-8"))
            for item in data:
                flag = FeatureFlag(**item)
                self._flags[flag.key] = flag
        except Exception:
            pass

    def _save(self) -> None:
        try:
            (_FLAGS_DIR / "flags.json").write_text(
                json.dumps([f.to_dict() for f in self._flags.values()], ensure_ascii=False, indent=2),
                encoding="utf-8",
            )
        except Exception:
            pass

    def register(self, key: str, default: bool = False, description: str = "") -> bool:
        if key not in self._flags:
            self._flags[key] = FeatureFlag(key=key, enabled=default, description=description)
            self._save()
        return self._flags[key].enabled

    def is_enabled(self, key: str, default: bool = False) -> bool:
        flag = self._flags.get(key)
        if not flag:
            return default
        return flag.enabled

    def set_enabled(self, key: str, enabled: bool) -> None:
        if key not in self._flags:
            self._flags[key] = FeatureFlag(key=key, enabled=enabled)
        else:
            self._flags[key].enabled = enabled
        self._save()

    def list_flags(self) -> List[Dict[str, Any]]:
        return [f.to_dict() for f in self._flags.values()]


feature_flags = FeatureFlags()
