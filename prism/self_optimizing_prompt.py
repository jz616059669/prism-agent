"""
PRISM Agent - Agent 自优化 Prompt
根据反馈自动调整 system prompt，无需人工调参
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


@dataclass
class PromptVariant:
    name: str
    prompt: str = ""
    success_count: int = 0
    failure_count: int = 0
    last_used: float = 0.0

    def success_rate(self) -> float:
        total = self.success_count + self.failure_count
        return self.success_count / total if total else 0.0


class SelfOptimizingPrompt:
    def __init__(self, base_prompt: str = "") -> None:
        self.base_prompt = base_prompt
        self._variants: List[PromptVariant] = []
        self._current: PromptVariant = PromptVariant(name="default", prompt=base_prompt)

    def record(self, success: bool) -> None:
        self._current.success_count += int(success)
        self._current.failure_count += int(not success)
        self._current.last_used = __import__("time").time()

    def optimize(self) -> str:
        if not self._variants:
            return self._current.prompt
        best = max(self._variants, key=lambda v: v.success_rate())
        if best.success_rate() > self._current.success_rate() and best.success_count >= 3:
            self._current = best
        return self._current.prompt

    def add_variant(self, name: str, prompt: str) -> PromptVariant:
        variant = PromptVariant(name=name, prompt=prompt)
        self._variants.append(variant)
        return variant


self_optimizing_prompt = SelfOptimizingPrompt()
