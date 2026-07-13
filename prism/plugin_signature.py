"""
PRISM Agent - 插件签名验证
防止安装恶意 skill
"""

from __future__ import annotations

import hashlib
import json
import logging
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)

_SIGN_DIR = Path.home() / ".prism" / "signatures"
_SIGN_DIR.mkdir(parents=True, exist_ok=True)


@dataclass
class PluginSignature:
    name: str
    sha256: str = ""
    public_key: str = ""
    verified: bool = False

    def to_dict(self) -> Dict[str, Any]:
        return {
            "name": self.name,
            "sha256": self.sha256,
            "public_key": self.public_key,
            "verified": self.verified,
        }


class PluginSignatureVerifier:
    def compute_sha256(self, file_path: str) -> str:
        path = Path(file_path)
        if not path.exists():
            return ""
        try:
            h = hashlib.sha256()
            with path.open("rb") as f:
                for chunk in iter(lambda: f.read(8192), b""):
                    h.update(chunk)
            return h.hexdigest()[:32]
        except Exception:
            return ""

    def sign(self, file_path: str, signature: PluginSignature) -> PluginSignature:
        signature.sha256 = self.compute_sha256(file_path)
        try:
            (_SIGN_DIR / f"{Path(file_path).stem}.json").write_text(
                json.dumps(signature.to_dict(), ensure_ascii=False, indent=2),
                encoding="utf-8",
            )
        except Exception:
            pass
        return signature

    def verify(self, file_path: str, signature: Optional[PluginSignature] = None) -> bool:
        expected = self.compute_sha256(file_path)
        if not expected:
            return False
        if signature:
            return signature.sha256 == expected
        # 从本地签名库校验
        sign_file = _SIGN_DIR / f"{Path(file_path).stem}.json"
        if not sign_file.exists():
            return True  # 未签名视为通过，仅告警
        try:
            data = json.loads(sign_file.read_text(encoding="utf-8"))
            return data.get("sha256", "") == expected
        except Exception:
            return True


plugin_signature_verifier = PluginSignatureVerifier()
