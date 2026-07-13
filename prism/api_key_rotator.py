"""
PRISM Agent - API 密钥轮换
自动轮换密钥，防泄露
"""

from __future__ import annotations

import json
import logging
import os
import secrets
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)

_KEY_DIR = Path.home() / ".prism" / "keys"
_KEY_DIR.mkdir(parents=True, exist_ok=True)


@dataclass
class ApiKey:
    id: str
    key: str = ""
    provider: str = ""
    created_at: float = field(default_factory=time.time)
    last_rotated: float = 0.0
    active: bool = True

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "key": self.key[:8] + "***",
            "provider": self.provider,
            "created_at": self.created_at,
            "last_rotated": self.last_rotated,
            "active": self.active,
        }


class ApiKeyRotator:
    def __init__(self, max_age_days: int = 90) -> None:
        self.max_age_days = max_age_days
        self._keys: Dict[str, ApiKey] = {}
        self._load()

    def _load(self) -> None:
        for key_file in _KEY_DIR.glob("*.json"):
            try:
                data = json.loads(key_file.read_text(encoding="utf-8"))
                key = ApiKey(**data)
                self._keys[key.id] = key
            except Exception:
                continue

    def add_key(self, provider: str, key: str) -> ApiKey:
        key_id = f"{provider}_{int(time.time())}"
        api_key = ApiKey(id=key_id, key=key, provider=provider)
        self._keys[key_id] = api_key
        self._save(api_key)
        return api_key

    def rotate(self, key_id: str) -> Optional[ApiKey]:
        key = self._keys.get(key_id)
        if not key:
            return None
        key.key = secrets.token_hex(16)
        key.last_rotated = time.time()
        self._save(key)
        logger.info("rotated api key %s", key_id)
        return key

    def should_rotate(self, key_id: str) -> bool:
        key = self._keys.get(key_id)
        if not key:
            return False
        age = time.time() - key.last_rotated if key.last_rotated else time.time() - key.created_at
        return age > self.max_age_days * 24 * 3600

    def list_keys(self) -> List[Dict[str, Any]]:
        return [k.to_dict() for k in self._keys.values()]

    def _save(self, key: ApiKey) -> None:
        try:
            (_KEY_DIR / f"{key.id}.json").write_text(
                json.dumps(key.to_dict(), ensure_ascii=False, indent=2),
                encoding="utf-8",
            )
        except Exception:
            pass


api_key_rotator = ApiKeyRotator()
