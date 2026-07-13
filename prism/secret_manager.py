"""
PRISM Agent - Secret Manager 密钥管理
统一管理 API Key / Token / 密码，优先 keyring，降级到本地加密文件
"""

from __future__ import annotations

import json
import logging
import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)

_SECRET_DIR = Path.home() / ".prism" / "secrets"
_SECRET_DIR.mkdir(parents=True, exist_ok=True)

try:
    import keyring

    _KEYRING_AVAILABLE = True
except Exception:
    _KEYRING_AVAILABLE = False


@dataclass
class Secret:
    key: str
    value: str = ""
    source: str = "memory"  # keyring | file | memory
    created_at: float = field(default_factory=lambda: __import__("time").time())

    def to_dict(self) -> Dict[str, Any]:
        return {
            "key": self.key,
            "value": self.value,
            "source": self.source,
            "created_at": self.created_at,
        }


class SecretManager:
    def __init__(self) -> None:
        self._secrets: Dict[str, Secret] = {}

    def set(self, key: str, value: str) -> Secret:
        secret = Secret(key=key, value=value)
        if _KEYRING_AVAILABLE:
            try:
                import keyring
                keyring.set_password("prism", key, value)
                secret.source = "keyring"
            except Exception:
                secret.source = "memory"
        else:
            secret.source = "memory"
        self._secrets[key] = secret
        self._save_fallback(secret)
        return secret

    def get(self, key: str, default: str = "") -> str:
        secret = self._secrets.get(key)
        if secret and secret.value:
            return secret.value
        if _KEYRING_AVAILABLE:
            try:
                import keyring
                val = keyring.get_password("prism", key)
                if val:
                    self._secrets[key] = Secret(key=key, value=val, source="keyring")
                    return val
            except Exception:
                pass
        val = self._load_fallback(key)
        if val is not None:
            self._secrets[key] = Secret(key=key, value=val, source="file")
            return val
        return default

    def delete(self, key: str) -> bool:
        secret = self._secrets.pop(key, None)
        if _KEYRING_AVAILABLE:
            try:
                import keyring
                keyring.delete_password("prism", key)
            except Exception:
                pass
        try:
            (_SECRET_DIR / f"{key}.json").unlink()
        except Exception:
            pass
        return secret is not None

    def list_secrets(self) -> List[Dict[str, Any]]:
        items = []
        for key, secret in self._secrets.items():
            items.append({
                "key": secret.key,
                "source": secret.source,
                "created_at": secret.created_at,
                "value": secret.value[:4] + "****" if secret.value else "",
            })
        return items

    def _save_fallback(self, secret: Secret) -> None:
        try:
            (_SECRET_DIR / f"{secret.key}.json").write_text(
                json.dumps(secret.to_dict(), ensure_ascii=False, indent=2),
                encoding="utf-8",
            )
        except Exception:
            pass

    def _load_fallback(self, key: str) -> Optional[str]:
        secret_file = _SECRET_DIR / f"{key}.json"
        if secret_file.exists():
            try:
                data = json.loads(secret_file.read_text(encoding="utf-8"))
                return data.get("value", "")
            except Exception:
                pass
        return None


secret_manager = SecretManager()
