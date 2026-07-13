"""
PRISM Agent - Graceful Degradation 优雅降级
模型/工具失败时自动降级，保持服务可用
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


@dataclass
class DegradationRule:
    name: str
    condition: str = ""  # error_pattern
    fallback: str = ""   # fallback model/tool/mode
    priority: int = 0

    def to_dict(self) -> Dict[str, Any]:
        return {
            "name": self.name,
            "condition": self.condition,
            "fallback": self.fallback,
            "priority": self.priority,
        }


@dataclass
class DegradationState:
    active: bool = False
    rule: str = ""
    reason: str = ""
    applied_at: float = 0.0

    def to_dict(self) -> Dict[str, Any]:
        return {
            "active": self.active,
            "rule": self.rule,
            "reason": self.reason,
            "applied_at": self.applied_at,
        }


class GracefulDegradation:
    def __init__(self) -> None:
        self._rules: List[DegradationRule] = []
        self._state = DegradationState()
        self._load_defaults()

    def _load_defaults(self) -> None:
        self._rules = [
            DegradationRule(name="model_timeout", condition="timeout", fallback="step-2-16k", priority=10),
            DegradationRule(name="rate_limit", condition="rate_limit", fallback="local_echo", priority=20),
            DegradationRule(name="model_500", condition="500", fallback="local_echo", priority=30),
            DegradationRule(name="model_401", condition="401", fallback="step-2-16k", priority=10),
            DegradationRule(name="tool_fail", condition="ModuleNotFoundError", fallback="skip_tool", priority=5),
        ]

    def evaluate(self, error_text: str) -> Optional[DegradationRule]:
        text = (error_text or "").lower()
        matched = []
        for rule in self._rules:
            if rule.condition.lower() in text:
                matched.append(rule)
        if not matched:
            return None
        matched.sort(key=lambda r: r.priority, reverse=True)
        return matched[0]

    def apply(self, rule: Optional[DegradationRule] = None, reason: str = "") -> DegradationState:
        selected = rule or self._rules[0] if self._rules else None
        if not selected:
            return self._state
        self._state.active = True
        self._state.rule = selected.name
        self._state.reason = reason
        self._state.applied_at = __import__("time").time()
        logger.warning("graceful degradation active: %s -> %s", selected.name, selected.fallback)
        return self._state

    def reset(self) -> DegradationState:
        self._state = DegradationState()
        return self._state

    def state(self) -> DegradationState:
        return self._state


graceful_degradation = GracefulDegradation()
