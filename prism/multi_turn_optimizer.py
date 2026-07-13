"""
PRISM Agent - 多轮优化
用户反馈后自动优化输出
"""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


@dataclass
class OptimizationRound:
    original: str = ""
    feedback: str = ""
    improved: str = ""
    score: float = 0.0

    def to_dict(self) -> Dict[str, Any]:
        return {
            "original": self.original,
            "feedback": self.feedback,
            "improved": self.improved,
            "score": self.score,
        }


class MultiTurnOptimizer:
    def optimize(self, original: str, feedback: str) -> OptimizationRound:
        improved = original
        lower_feedback = (feedback or "").lower()
        if "太长" in lower_feedback or "too long" in lower_feedback:
            improved = self._shorten(improved)
        elif "太短" in lower_feedback or "too short" in lower_feedback:
            improved = self._expand(improved)
        elif "更专业" in lower_feedback or "professional" in lower_feedback:
            improved = "[正式]\n" + improved
        elif "口语" in lower_feedback or "casual" in lower_feedback:
            improved = "[轻松]\n" + improved
        else:
            improved = improved + "\n\n（已根据反馈调整）"
        score = 0.7 if improved != original else 1.0
        return OptimizationRound(original=original, feedback=feedback, improved=improved, score=score)

    def _shorten(self, text: str) -> str:
        lines = [line for line in (text or "").splitlines() if line.strip()]
        if len(lines) <= 3:
            return text
        return "\n".join(lines[:3]) + "\n..."

    def _expand(self, text: str) -> str:
        return (text or "") + "\n\n补充：更多细节请参考相关文档。"


multi_turn_optimizer = MultiTurnOptimizer()
