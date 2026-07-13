"""
PRISM Agent - 性能预算
函数执行时间预算，超时告警
"""

from __future__ import annotations

import json
import logging
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)

_BUDGET_DIR = Path.home() / ".prism" / "perf_budget"
_BUDGET_DIR.mkdir(parents=True, exist_ok=True)


@dataclass
class BudgetRule:
    name: str
    budget_ms: float = 500.0
    window_size: int = 20

    def to_dict(self) -> Dict[str, Any]:
        return {
            "name": self.name,
            "budget_ms": self.budget_ms,
            "window_size": self.window_size,
        }


@dataclass
class BudgetViolation:
    name: str
    actual_ms: float = 0.0
    budget_ms: float = 0.0
    ts: float = field(default_factory=time.time)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "name": self.name,
            "actual_ms": round(self.actual_ms, 2),
            "budget_ms": self.budget_ms,
            "ts": self.ts,
        }


class PerformanceBudget:
    def __init__(self) -> None:
        self._rules: Dict[str, BudgetRule] = {}
        self._samples: Dict[str, List[float]] = {}
        self._violations: List[BudgetViolation] = []
        self._load_rules()

    def _load_rules(self) -> None:
        rule_file = _BUDGET_DIR / "rules.json"
        if not rule_file.exists():
            return
        try:
            for item in json.loads(rule_file.read_text(encoding="utf-8")):
                rule = BudgetRule(**item)
                self._rules[rule.name] = rule
        except Exception:
            pass

    def set_budget(self, name: str, budget_ms: float, window_size: int = 20) -> BudgetRule:
        rule = BudgetRule(name=name, budget_ms=budget_ms, window_size=window_size)
        self._rules[name] = rule
        self._save_rules()
        return rule

    def record(self, name: str, actual_ms: float) -> Optional[BudgetViolation]:
        rule = self._rules.get(name)
        if not rule:
            return None
        self._samples.setdefault(name, []).append(actual_ms)
        self._samples[name] = self._samples[name][-rule.window_size:]
        avg = sum(self._samples[name]) / len(self._samples[name])
        if avg > rule.budget_ms:
            violation = BudgetViolation(name=name, actual_ms=avg, budget_ms=rule.budget_ms)
            self._violations.append(violation)
            logger.warning("budget exceeded: %s avg %.1f ms > budget %.1f ms", name, avg, rule.budget_ms)
            return violation
        return None

    def status(self) -> Dict[str, Any]:
        return {
            "rules": [r.to_dict() for r in self._rules.values()],
            "recent_violations": [v.to_dict() for v in self._violations[-20:]],
        }

    def _save_rules(self) -> None:
        try:
            (_BUDGET_DIR / "rules.json").write_text(
                json.dumps([r.to_dict() for r in self._rules.values()], ensure_ascii=False, indent=2),
                encoding="utf-8",
            )
        except Exception:
            pass


performance_budget = PerformanceBudget()
