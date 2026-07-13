"""
PRISM Agent - 零信任代理
每个外部请求经过最小权限检查 + 临时令牌
"""

from __future__ import annotations

import logging
import time
import uuid
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


@dataclass
class ZeroTrustToken:
    token: str = field(default_factory=lambda: uuid.uuid4().hex)
    subject: str = ""
    scope: List[str] = field(default_factory=list)
    max_age: int = 300
    created_at: float = field(default_factory=time.time)

    def is_valid(self) -> bool:
        return time.time() - self.created_at < self.max_age

    def to_dict(self) -> Dict[str, Any]:
        return {
            "token": self.token,
            "subject": self.subject,
            "scope": list(self.scope),
            "max_age": self.max_age,
            "created_at": self.created_at,
        }


class ZeroTrustProxy:
    def __init__(self) -> None:
        self._tokens: Dict[str, ZeroTrustToken] = {}
        self._denied: List[Dict[str, Any]] = []

    def mint_token(self, subject: str, scope: List[str], max_age: int = 300) -> ZeroTrustToken:
        token = ZeroTrustToken(subject=subject, scope=scope, max_age=max_age)
        self._tokens[token.token] = token
        return token

    def validate(self, token: str, required_scope: List[str]) -> bool:
        item = self._tokens.get(token)
        if not item or not item.is_valid():
            return False
        for scope in required_scope:
            if scope not in item.scope:
                self._denied.append({"token": token, "required_scope": required_scope, "ts": time.time()})
                return False
        return True

    def revoke(self, token: str) -> bool:
        return self._tokens.pop(token, None) is not None

    def audit(self, limit: int = 50) -> List[Dict[str, Any]]:
        return self._denied[-limit:]


zero_trust_proxy = ZeroTrustProxy()
