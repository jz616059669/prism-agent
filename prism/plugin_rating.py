"""
PRISM Agent - 插件评分系统
本地评分 + 评论
"""

from __future__ import annotations

import json
import logging
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)

_RATING_DIR = Path.home() / ".prism" / "ratings"
_RATING_DIR.mkdir(parents=True, exist_ok=True)


@dataclass
class PluginRating:
    name: str
    score: float = 0.0
    count: int = 0
    reviews: List[Dict[str, Any]] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "name": self.name,
            "score": round(self.score, 1),
            "count": self.count,
            "reviews": list(self.reviews),
        }


class PluginRatingSystem:
    def __init__(self) -> None:
        self._ratings: Dict[str, PluginRating] = {}
        self._load()

    def _load(self) -> None:
        for rating_file in _RATING_DIR.glob("*.json"):
            try:
                data = json.loads(rating_file.read_text(encoding="utf-8"))
                rating = PluginRating(**data)
                self._ratings[rating.name] = rating
            except Exception:
                continue

    def rate(self, name: str, score: float, review: str = "") -> PluginRating:
        rating = self._ratings.get(name) or PluginRating(name=name)
        rating.count += 1
        rating.score = ((rating.score * (rating.count - 1)) + score) / rating.count
        if review:
            rating.reviews.append({"text": review, "score": score, "ts": time.time()})
        self._ratings[name] = rating
        self._save(rating)
        return rating

    def get(self, name: str) -> Optional[PluginRating]:
        return self._ratings.get(name)

    def list_ratings(self) -> List[Dict[str, Any]]:
        return [r.to_dict() for r in self._ratings.values()]

    def _save(self, rating: PluginRating) -> None:
        try:
            (_RATING_DIR / f"{rating.name}.json").write_text(
                json.dumps(rating.to_dict(), ensure_ascii=False, indent=2),
                encoding="utf-8",
            )
        except Exception:
            pass


plugin_rating_system = PluginRatingSystem()
