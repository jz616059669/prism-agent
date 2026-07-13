"""
PRISM Agent - 用户画像/偏好学习
记录用户偏好，自动调整行为
"""

from __future__ import annotations

import json
import logging
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)

_PROFILE_DIR = Path.home() / ".prism" / "profile"
_PROFILE_DIR.mkdir(parents=True, exist_ok=True)


@dataclass
class UserPreference:
    key: str
    value: Any = None
    confidence: float = 0.0
    updated_at: float = field(default_factory=time.time)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "key": self.key,
            "value": self.value,
            "confidence": round(self.confidence, 2),
            "updated_at": self.updated_at,
        }


class UserProfile:
    def __init__(self) -> None:
        self._preferences: Dict[str, UserPreference] = {}
        self._load()

    def _load(self) -> None:
        profile_file = _PROFILE_DIR / "profile.json"
        if not profile_file.exists():
            return
        try:
            data = json.loads(profile_file.read_text(encoding="utf-8"))
            for item in data:
                pref = UserPreference(**item)
                self._preferences[pref.key] = pref
        except Exception:
            pass

    def set(self, key: str, value: Any, confidence: float = 1.0) -> UserPreference:
        pref = self._preferences.get(key)
        if pref:
            pref.value = value
            pref.confidence = max(pref.confidence, confidence)
            pref.updated_at = time.time()
        else:
            pref = UserPreference(key=key, value=value, confidence=confidence)
            self._preferences[key] = pref
        self._save()
        return pref

    def get(self, key: str, default: Any = None) -> Any:
        pref = self._preferences.get(key)
        if not pref:
            return default
        return pref.value

    def all(self) -> List[Dict[str, Any]]:
        return [pref.to_dict() for pref in self._preferences.values()]

    def _save(self) -> None:
        try:
            (_PROFILE_DIR / "profile.json").write_text(
                json.dumps(self.all(), ensure_ascii=False, indent=2),
                encoding="utf-8",
            )
        except Exception:
            pass


user_profile = UserProfile()
