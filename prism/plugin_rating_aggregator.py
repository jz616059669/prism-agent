"""
PRISM Agent - 插件市场评分聚合
本地聚合评分，结合插件评分系统
"""

from __future__ import annotations

import json
import logging
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


class PluginRatingAggregator:
    def aggregate(self, ratings: List[Dict[str, Any]]) -> Dict[str, Any]:
        if not ratings:
            return {"count": 0, "average": 0.0, "distribution": {}}
        scores = [r.get("score", 0.0) for r in ratings if r.get("score") is not None]
        count = len(scores)
        average = sum(scores) / count if count else 0.0
        distribution: Dict[str, int] = {}
        for r in ratings:
            bucket = str(int(r.get("score", 0) / 2) * 2)
            distribution[bucket] = distribution.get(bucket, 0) + 1
        return {"count": count, "average": round(average, 1), "distribution": distribution}

    def top_plugins(self, ratings: List[Dict[str, Any]], limit: int = 10) -> List[Dict[str, Any]]:
        ranked = sorted(ratings, key=lambda r: (r.get("score", 0), r.get("count", 0)), reverse=True)
        return ranked[:limit]


plugin_rating_aggregator = PluginRatingAggregator()
