"""
PRISM Agent - 智能模型路由器
按任务复杂度自动选模型，省钱+保质量
"""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


@dataclass
class ModelRoute:
    name: str
    provider: str = ""
    base_url: str = ""
    model: str = ""
    max_tokens: int = 4096
    cost_per_1k: float = 0.0
    strength: str = "general"  # cheap | general | strong | reasoning

    def to_dict(self) -> Dict[str, Any]:
        return {
            "name": self.name,
            "provider": self.provider,
            "base_url": self.base_url,
            "model": self.model,
            "max_tokens": self.max_tokens,
            "cost_per_1k": self.cost_per_1k,
            "strength": self.strength,
        }


@dataclass
class TaskHint:
    text_length: int = 0
    code: bool = False
    web_search: bool = False
    reasoning: bool = False
    summary: bool = False
    translation: bool = False


class SmartModelRouter:
    def __init__(self, routes: Optional[List[ModelRoute]] = None) -> None:
        self._routes = routes or [
            ModelRoute(name="cheap", provider="stepfun", base_url="https://api.stepfun.com/step_plan/v1", model="step-2-16k", max_tokens=4096, cost_per_1k=0.001, strength="cheap"),
            ModelRoute(name="general", provider="stepfun", base_url="https://api.stepfun.com/step_plan/v1", model="step-3.7-flash", max_tokens=4096, cost_per_1k=0.002, strength="general"),
            ModelRoute(name="strong", provider="stepfun", base_url="https://api.stepfun.com/step_plan/v1", model="step-3.7-flash", max_tokens=4096, cost_per_1k=0.004, strength="strong"),
        ]

    def pick(self, task: str, prefer_cheap: bool = True) -> ModelRoute:
        hint = self._detect(task)
        if hint.reasoning or hint.code or hint.web_search:
            for route in self._routes:
                if route.strength == "strong":
                    return route
            return self._routes[-1]
        if hint.summary and prefer_cheap:
            for route in self._routes:
                if route.strength == "cheap":
                    return route
            return self._routes[0]
        for route in self._routes:
            if route.strength == "general":
                return route
        return self._routes[0]

    def _detect(self, text: str) -> TaskHint:
        t = (text or "").lower()
        return TaskHint(
            text_length=len(text),
            code=bool(re.search(r"```|def |class |import |\\.py\\b", t)),
            web_search=bool(re.search(r"搜索|search|查询|最新|新闻|news", t)),
            reasoning=bool(re.search(r"推理|reason|分析|分析|总结|原因|因果", t)),
            summary=bool(re.search(r"摘要|总结|概括|提炼|summar", t)),
            translation=bool(re.search(r"翻译|translate|translat", t)),
        )


smart_model_router = SmartModelRouter()
