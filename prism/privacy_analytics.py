"""
PRISM Agent - 隐私保护分析
本地聚合统计，不泄露个体数据到外部
"""

from __future__ import annotations

import json
import logging
import math
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)

_ANALYTICS_DIR = Path.home() / ".prism" / "analytics"
_ANALYTICS_DIR.mkdir(parents=True, exist_ok=True)


@dataclass
class AnalyticsBucket:
    key: str
    count: int = 0
    sum_value: float = 0.0

    def to_dict(self) -> Dict[str, Any]:
        return {
            "key": self.key,
            "count": self.count,
            "sum_value": self.sum_value,
            "avg_value": self.sum_value / self.count if self.count else 0.0,
        }


class PrivacyPreservingAnalytics:
    def __init__(self) -> None:
        self._buckets: Dict[str, AnalyticsBucket] = {}

    def record(self, key: str, value: float = 1.0) -> None:
        if key not in self._buckets:
            self._buckets[key] = AnalyticsBucket(key=key)
        self._buckets[key].count += 1
        self._buckets[key].sum_value += value
        self._save()

    def summary(self) -> List[Dict[str, Any]]:
        return [b.to_dict() for b in self._buckets.values()]

    def differential_privacy_noise(self, epsilon: float = 1.0) -> List[Dict[str, Any]]:
        """加噪声保护个体：epsilon 越小越隐私"""
        scale = 1.0 / max(epsilon, 0.1)
        results = []
        for b in self._buckets.values():
            noise = math.floor(__import__("random").uniform(-scale, scale))
            results.append({
                "key": b.key,
                "noisy_count": max(0, b.count + noise),
                "noisy_avg": round((b.sum_value / b.count if b.count else 0.0) + noise * 0.1, 3),
            })
        return results

    def _save(self) -> None:
        try:
            (_ANALYTICS_DIR / "analytics.json").write_text(
                json.dumps([b.to_dict() for b in self._buckets.values()], ensure_ascii=False, indent=2),
                encoding="utf-8",
            )
        except Exception:
            pass


privacy_analytics = PrivacyPreservingAnalytics()
