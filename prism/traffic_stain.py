"""
PRISM Agent - 流量染色
灰度发布：按用户/比例路由模型
"""

from __future__ import annotations

import logging
import random
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


@dataclass
class TrafficRule:
    name: str
    model: str = ""
    ratio: float = 1.0
    users: List[str] = field(default_factory=list)
    tags: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "name": self.name,
            "model": self.model,
            "ratio": self.ratio,
            "users": list(self.users),
            "tags": list(self.tags),
        }


class TrafficStain:
    def __init__(self) -> None:
        self._rules: List[TrafficRule] = []
        self._default_model: str = ""

    def set_default_model(self, model: str) -> None:
        self._default_model = model

    def add_rule(self, rule: TrafficRule) -> None:
        self._rules.append(rule)

    def route(self, user: str = "", tags: Optional[List[str]] = None) -> str:
        for rule in self.rules:
            if user and user in rule.users:
                return rule.model
            if tags and set(rule.tags).intersection(set(tags or [])):
                return rule.model
        if self._rules and random.random() < self._rules[0].ratio:
            return self._rules[0].model
        return self._default_model

    @property
    def rules(self) -> List[TrafficRule]:
        return sorted(self._rules, key=lambda r: r.ratio or 0, reverse=True)


traffic_stain = TrafficStain()
