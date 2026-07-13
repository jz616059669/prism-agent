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
        self._stats: Dict[str, Dict[str, float]] = {r.name: {"success": 0.0, "fail": 0.0, "latency": 0.0} for r in self._routes}

    def pick(self, task: str, prefer_cheap: bool = True) -> ModelRoute:
        hint = self._detect(task)
        candidates = self._score_routes(hint, prefer_cheap)
        return candidates[0][1] if candidates else self._routes[-1]

    def record(self, route_name: str, success: bool, latency_ms: float = 0.0) -> None:
        stats = self._stats.get(route_name)
        if not stats:
            return
        if success:
            stats["success"] += 1.0
        else:
            stats["fail"] += 1.0
        stats["latency"] = latency_ms

    def _score_routes(self, hint: TaskHint, prefer_cheap: bool):
        scored: List[tuple[float, ModelRoute]] = []
        for route in self._routes:
            score = 0.0
            if hint.reasoning or hint.code or hint.web_search:
                if route.strength == "strong":
                    score += 3.0
                elif route.strength == "general":
                    score += 1.0
            elif hint.summary and prefer_cheap:
                if route.strength == "cheap":
                    score += 3.0
                elif route.strength == "general":
                    score += 2.0
            else:
                if route.strength == "general":
                    score += 3.0
                elif route.strength == "cheap":
                    score += 2.0
            stats = self._stats.get(route.name, {})
            total = stats.get("success", 0.0) + stats.get("fail", 0.0)
            if total > 0:
                success_rate = stats.get("success", 0.0) / total
                score += success_rate * 2.0
                latency = stats.get("latency", 0.0)
                if latency > 0:
                    score += max(0.0, 1.0 - min(latency / 5000.0, 1.0))
            scored.append((score, route))
        scored.sort(key=lambda x: x[0], reverse=True)
        return scored

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
