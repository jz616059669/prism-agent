"""
PRISM Agent - 技能推荐
根据用户任务自动推荐技能
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


@dataclass
class SkillRecommendation:
    name: str
    reason: str = ""
    score: float = 0.0

    def to_dict(self) -> Dict[str, Any]:
        return {
            "name": self.name,
            "reason": self.reason,
            "score": self.score,
        }


class SkillRecommender:
    def __init__(self) -> None:
        self._keywords: Dict[str, List[str]] = {
            "search": ["web_search", "web_extract", "browser"],
            "write": ["writer", "markdown", "notebook"],
            "code": ["coder", "sandbox", "code_review", "code_formatter"],
            "data": ["data_pipeline", "code_search", "benchmark"],
            "memory": ["memory", "knowledge_graph", "cross_session_search"],
            "security": ["prompt_security", "permissions", "sandbox"],
        }

    def recommend(self, task: str, top_k: int = 5) -> List[SkillRecommendation]:
        recommendations: List[SkillRecommendation] = []
        text = (task or "").lower()
        for category, skills in self._keywords.items():
            if any(token in text for token in category.split("_")):
                for skill in skills:
                    recommendations.append(SkillRecommendation(name=skill, reason=f"匹配分类: {category}", score=1.0))
        seen = set()
        unique: List[SkillRecommendation] = []
        for rec in recommendations:
            if rec.name not in seen:
                seen.add(rec.name)
                unique.append(rec)
        unique.sort(key=lambda r: r.score, reverse=True)
        return unique[:top_k]


skill_recommender = SkillRecommender()
