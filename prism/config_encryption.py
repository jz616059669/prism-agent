"""
PRISM Agent - 配置加密
配置文件加密存储，防止敏感配置泄露
"""

from __future__ import annotations

import base64
import json
import logging
import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, Optional

logger = logging.getLogger(__name__)

_CRYPTO_DIR = Path.home() / ".prism" / "crypto"
_KEY_FILE = _CRYPTO_DIR / "key.bin"


def _get_or_create_key() -> bytes:
    try:
        _CRYPTO_DIR.mkdir(parents=True, exist_ok=True)
        if _KEY_FILE.exists():
            try:
                return _KEY_FILE.read_bytes()
            except Exception:
                pass
        key = os.urandom(32)
        try:
            _KEY_FILE.write_bytes(key)
            try:
                os.chmod(str(_KEY_FILE), 0o600)
            except Exception:
                pass
        except Exception:
            pass
        return key
    except Exception:
        return os.urandom(32)


class ConfigEncryption:
    def __init__(self) -> None:
        self._available = None  # 延迟检测
        self._hkdf = None
        self._fernet = None
        self._key = None
        self._key_loaded = False

    def _ensure_key(self) -> bytes:
        if not self._key_loaded:
            self._key = _get_or_create_key()
            self._key_loaded = True
        return self._key

    def _ensure(self) -> bool:
        if self._available is None:
            try:
                from cryptography.fernet import Fernet
                from cryptography.hazmat.primitives import hashlib
                from cryptography.hazmat.primitives.kdf.hkdf import HKDF
                self._available = True
                self._hkdf = HKDF
                self._fernet = Fernet
            except Exception:
                self._available = False
        return bool(self._available)

    def _get_fernet(self):
        if not self._ensure() or self._fernet is None:
            return None
        from cryptography.hazmat.primitives import hashlib
        from cryptography.hazmat.backends import default_backend
        hkdf = self._hkdf(algorithm=hashlib.SHA256(), length=32, salt=None, info=b"prism-config", backend=default_backend())
        key = hkdf.derive(self._ensure_key())
        return self._fernet(base64.urlsafe_b64encode(key))

    def encrypt(self, plaintext: str) -> str:
        fernet = self._get_fernet()
        if not fernet:
            return plaintext
        try:
            return fernet.encrypt(plaintext.encode("utf-8")).decode("utf-8")
        except Exception:
            return plaintext

    def decrypt(self, ciphertext: str) -> str:
        fernet = self._get_fernet()
        if not fernet:
            return ciphertext
        try:
            return fernet.decrypt(ciphertext.encode("utf-8")).decode("utf-8")
        except Exception:
            return ciphertext

    def is_encrypted(self, value: Any) -> bool:
        text = str(value or "")
        return text.startswith("gAAAAAB") or text.startswith("ENC:")


_config_encryption_singleton: Optional[ConfigEncryption] = None


def get_config_encryption() -> ConfigEncryption:
    global _config_encryption_singleton
    if _config_encryption_singleton is None:
        _config_encryption_singleton = ConfigEncryption()
    return _config_encryption_singleton
