"""
PRISM Agent - Usage quota 配额
按用户/项目限制 API 调用量
"""

from __future__ import annotations

import json
import logging
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)

_QUOTA_DIR = Path.home() / ".prism" / "quota"
_QUOTA_DIR.mkdir(parents=True, exist_ok=True)


@dataclass
class QuotaRule:
    key: str
    limit: int = 1000
    window: int = 3600
    used: int = 0
    reset_at: float = 0.0

    def to_dict(self) -> Dict[str, Any]:
        return {
            "key": self.key,
            "limit": self.limit,
            "window": self.window,
            "used": self.used,
            "reset_at": self.reset_at,
        }


class UsageQuota:
    def __init__(self) -> None:
        self._rules: Dict[str, QuotaRule] = {}
        self._load()

    def _load(self) -> None:
        quota_file = _QUOTA_DIR / "quota.json"
        if not quota_file.exists():
            return
        try:
            data = json.loads(quota_file.read_text(encoding="utf-8"))
            for item in data:
                rule = QuotaRule(**item)
                self._rules[rule.key] = rule
        except Exception:
            pass

    def _save(self) -> None:
        try:
            (_QUOTA_DIR / "quota.json").write_text(
                json.dumps([r.to_dict() for r in self._rules.values()], ensure_ascii=False, indent=2),
                encoding="utf-8",
            )
        except Exception:
            pass

    def allow(self, key: str, amount: int = 1) -> bool:
        if key not in self._rules:
            self._rules[key] = QuotaRule(key=key)
        rule = self._rules[key]
        now = time.time()
        if now >= rule.reset_at:
            rule.used = 0
            rule.reset_at = now + rule.window
        if rule.used + amount > rule.limit:
            return False
        rule.used += amount
        self._save()
        return True

    def set_limit(self, key: str, limit: int, window: int = 3600) -> QuotaRule:
        if key not in self._rules:
            self._rules[key] = QuotaRule(key=key)
        rule = self._rules[key]
        rule.limit = limit
        rule.window = window
        self._save()
        return rule

    def status(self, key: str) -> Dict[str, Any]:
        rule = self._rules.get(key)
        if not rule:
            return {"key": key, "limit": 0, "used": 0, "remaining": 0}
        return rule.to_dict()


usage_quota = UsageQuota()
