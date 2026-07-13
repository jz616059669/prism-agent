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
_CRYPTO_DIR.mkdir(parents=True, exist_ok=True)
_KEY_FILE = _CRYPTO_DIR / "key.bin"


def _get_or_create_key() -> bytes:
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


class ConfigEncryption:
    def __init__(self) -> None:
        self._key = _get_or_create_key()
        self._available = None  # 延迟检测

    def _ensure(self) -> bool:
        if self._available is None:
            try:
                from cryptography.fernet import Fernet  # noqa: F401
                from cryptography.hazmat.primitives import hashlib  # noqa: F401
                from cryptography.hazmat.primitives.kdf.hkdf import HKDF  # noqa: F401
                self._available = True
            except Exception:
                self._available = False
        return bool(self._available)

    def encrypt(self, plaintext: str) -> str:
        if not self._ensure():
            return plaintext
        try:
            from cryptography.hazmat.primitives.kdf.hkdf import HKDF
            from cryptography.hazmat.primitives import hashlib
            from cryptography.hazmat.backends import default_backend
            from cryptography.fernet import Fernet
            hkdf = HKDF(algorithm=hashlib.SHA256(), length=32, salt=None, info=b"prism-config", backend=default_backend())
            key = hkdf.derive(self._key)
            return Fernet(base64.urlsafe_b64encode(key)).encrypt(plaintext.encode("utf-8")).decode("utf-8")
        except Exception:
            return plaintext

    def decrypt(self, ciphertext: str) -> str:
        if not self._ensure():
            return ciphertext
        try:
            from cryptography.hazmat.primitives.kdf.hkdf import HKDF
            from cryptography.hazmat.primitives import hashlib
            from cryptography.hazmat.backends import default_backend
            from cryptography.fernet import Fernet
            hkdf = HKDF(algorithm=hashlib.SHA256(), length=32, salt=None, info=b"prism-config", backend=default_backend())
            key = hkdf.derive(self._key)
            return Fernet(base64.urlsafe_b64encode(key)).decrypt(ciphertext.encode("utf-8")).decode("utf-8")
        except Exception:
            return ciphertext

    def is_encrypted(self, value: Any) -> bool:
        text = str(value or "")
        return text.startswith("gAAAAAB") or text.startswith("ENC:")


config_encryption = ConfigEncryption()
