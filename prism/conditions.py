"""
PRISM Agent - Conditional Triggers
条件规则：用于定时任务在触发前做前置判断
"""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)

_RULES_DIR = Path.home() / ".prism" / "rules"
_RULES_DIR.mkdir(parents=True, exist_ok=True)


@dataclass
class ConditionRule:
    id: str
    name: str = ""
    expression: str = ""  # 简单表达式，如 `usage.success_rate > 80`
    enabled: bool = True
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "name": self.name,
            "expression": self.expression,
            "enabled": self.enabled,
            "metadata": self.metadata,
        }


class ConditionEngine:
    def __init__(self) -> None:
        self._rules: Dict[str, ConditionRule] = {}
        self._load_rules()

    def _load_rules(self) -> None:
        for rule_file in _RULES_DIR.glob("*.json"):
            try:
                data = json.loads(rule_file.read_text(encoding="utf-8"))
                rule = ConditionRule(**data)
                self._rules[rule.id] = rule
            except Exception:
                continue

    def evaluate(self, context: Dict[str, Any]) -> Dict[str, Any]:
        results: Dict[str, Any] = {"passed": [], "failed": [], "blocked": []}
        for rule in self._rules.values():
            if not rule.enabled:
                continue
            try:
                ok = self._eval_expr(rule.expression, context)
                if ok:
                    results["passed"].append(rule.id)
                else:
                    results["failed"].append(rule.id)
            except Exception as exc:
                results["blocked"].append({"id": rule.id, "error": str(exc)})
        return results

    def should_proceed(self, context: Dict[str, Any], require_all: bool = False) -> bool:
        res = self.evaluate(context)
        if not res["passed"] and not res["failed"]:
            return True
        if require_all:
            return len(res["failed"]) == 0 and len(res["blocked"]) == 0
        return len(res["passed"]) > 0

    def add_rule(self, rule: ConditionRule) -> ConditionRule:
        self._rules[rule.id] = rule
        self._save_rule(rule)
        return rule

    def remove_rule(self, rule_id: str) -> bool:
        if rule_id not in self._rules:
            return False
        del self._rules[rule_id]
        rule_file = _RULES_DIR / f"{rule_id}.json"
        try:
            rule_file.unlink()
        except Exception:
            pass
        return True

    def list_rules(self) -> List[Dict[str, Any]]:
        return [r.to_dict() for r in self._rules.values()]

    def _save_rule(self, rule: ConditionRule) -> None:
        try:
            (_RULES_DIR / f"{rule.id}.json").write_text(
                json.dumps(rule.to_dict(), ensure_ascii=False, indent=2), encoding="utf-8"
            )
        except Exception:
            pass

    def _eval_expr(self, expr: str, ctx: Dict[str, Any]) -> bool:
        safe_ctx = {"__builtins__": {}, **ctx}
        try:
            return bool(eval(expr, safe_ctx, {}))
        except Exception:
            return False


# 全局单例
condition_engine = ConditionEngine()
