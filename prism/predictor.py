"""
PRISM Agent - 预测性自动补全
基于历史对话预测下一个输入/操作
"""

from __future__ import annotations

import logging
from collections import Counter
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


@dataclass
class Suggestion:
    text: str
    score: float = 0.0
    source: str = "history"


class Predictor:
    def __init__(self) -> None:
        self._user_inputs: List[str] = []
        self._pair_counter: Counter = Counter()

    def learn(self, user_input: str, next_user_input: str) -> None:
        self._user_inputs.append(user_input)
        self._pair_counter[(user_input, next_user_input)] += 1

    def suggest(self, current_text: str, max_items: int = 5) -> List[Suggestion]:
        if not current_text:
            return []
        suggestions: List[Suggestion] = []
        # 基于历史相似前缀
        for prev, nxt in self._pair_counter:
            if current_text in prev or prev in current_text:
                suggestions.append(Suggestion(text=nxt, score=self._pair_counter[(prev, nxt)], source="pair"))
        # 去重
        seen = set()
        unique: List[Suggestion] = []
        for s in suggestions:
            if s.text not in seen:
                seen.add(s.text)
                unique.append(s)
        unique.sort(key=lambda s: s.score, reverse=True)
        return unique[:max_items]


predictor = Predictor()
