"""
PRISM Agent - 知识蒸馏
把大模型输出提炼成小模型/本地规则
"""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)

_DISTILL_DIR = Path.home() / ".prism" / "distill"
_DISTILL_DIR.mkdir(parents=True, exist_ok=True)


@dataclass
class DistilledRule:
    name: str
    condition: str = ""
    action: str = ""
    confidence: float = 0.0
    source_count: int = 0

    def to_dict(self) -> Dict[str, Any]:
        return {
            "name": self.name,
            "condition": self.condition,
            "action": self.action,
            "confidence": self.confidence,
            "source_count": self.source_count,
        }


class KnowledgeDistiller:
    def __init__(self) -> None:
        self._rules: List[DistilledRule] = []

    def distill_from_pairs(self, pairs: List[Dict[str, str]]) -> List[DistilledRule]:
        rules: List[DistilledRule] = []
        for pair in pairs:
            question = str(pair.get("question", "") or "").strip()
            answer = str(pair.get("answer", "") or "").strip()
            if not question or not answer:
                continue
            rule_name = question[:32].replace(" ", "_")
            rule = DistilledRule(name=rule_name, condition=question, action=answer, confidence=1.0, source_count=1)
            rules.append(rule)
        self._rules.extend(rules)
        return rules

    def export_rules(self) -> List[Dict[str, Any]]:
        return [r.to_dict() for r in self._rules]

    def load_rules(self) -> List[Dict[str, Any]]:
        return self.export_rules()


knowledge_distiller = KnowledgeDistiller()
