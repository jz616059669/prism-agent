"""
PRISM Agent - Privacy Mode
本地-only 模式：禁用所有外部 API，只跑 sandbox/RAG/本地模型
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


@dataclass
class PrivacyPolicy:
    enabled: bool = False
    allow_external_api: bool = False
    allow_network: bool = False
    allow_web_search: bool = False
    allow_browser: bool = False
    allowed_local: List[str] = field(default_factory=lambda: ["sandbox", "rag", "local_model", "file", "terminal"])

    def to_dict(self) -> Dict[str, Any]:
        return {
            "enabled": self.enabled,
            "allow_external_api": self.allow_external_api,
            "allow_network": self.allow_network,
            "allow_web_search": self.allow_web_search,
            "allow_browser": self.allow_browser,
            "allowed_local": list(self.allowed_local),
        }


class PrivacyMode:
    def __init__(self) -> None:
        self._policy = PrivacyPolicy()

    def enable(self) -> PrivacyPolicy:
        self._policy.enabled = True
        self._policy.allow_external_api = False
        self._policy.allow_network = False
        self._policy.allow_web_search = False
        self._policy.allow_browser = False
        return self._policy

    def disable(self) -> PrivacyPolicy:
        self._policy.enabled = False
        return self._policy

    def is_enabled(self) -> bool:
        return self._policy.enabled

    def is_allowed(self, tool: str) -> bool:
        if not self._policy.enabled:
            return True
        return tool in self._policy.allowed_local


privacy_mode = PrivacyMode()
