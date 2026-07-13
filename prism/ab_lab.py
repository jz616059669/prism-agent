"""
PRISM Agent - Prompt A/B 实验室
自动对比同一任务的不同 prompt，记录胜出者
"""

from __future__ import annotations

import logging
import time
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


@dataclass
class ABRecord:
    task: str
    prompt_a: str
    prompt_b: str
    winner: str = ""
    score_a: float = 0.0
    score_b: float = 0.0
    ts: float = field(default_factory=time.time)
    metadata: Dict[str, Any] = field(default_factory=dict)


class ABLab:
    def __init__(self) -> None:
        self._records: List[ABRecord] = []

    def run(self, task: str, prompt_a: str, prompt_b: str, judge_fn) -> ABRecord:
        record = ABRecord(task=task, prompt_a=prompt_a, prompt_b=prompt_b)
        try:
            score_a = judge_fn(task, prompt_a)
            score_b = judge_fn(task, prompt_b)
            record.score_a = float(score_a)
            record.score_b = float(score_b)
            record.winner = "a" if score_a >= score_b else "b"
        except Exception as exc:
            logger.debug("ab lab failed: %s", exc)
        self._records.append(record)
        return record

    def leaderboard(self) -> Dict[str, Any]:
        wins: Dict[str, int] = {}
        for rec in self._records:
            if rec.winner:
                wins[rec.winner] = wins.get(rec.winner, 0) + 1
        return {"total": len(self._records), "wins": wins}


ab_lab = ABLab()
