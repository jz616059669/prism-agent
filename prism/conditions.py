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
        try:
            return bool(self._safe_eval(expr, ctx))
        except Exception:
            return False

    @staticmethod
    def _safe_eval(expr: str, ctx: Dict[str, Any]) -> Any:
        """受限 AST 求值：仅允许字面量、比较、布尔、算术、属性/下标访问。"""
        import ast
        import operator

        _OPS: Dict[type, Callable[[Any, Any], Any]] = {
            ast.Add: operator.add,
            ast.Sub: operator.sub,
            ast.Mult: operator.mul,
            ast.Div: operator.truediv,
            ast.Mod: operator.mod,
            ast.Eq: operator.eq,
            ast.NotEq: operator.ne,
            ast.Lt: operator.lt,
            ast.LtE: operator.le,
            ast.Gt: operator.gt,
            ast.GtE: operator.ge,
            ast.And: lambda a, b: a and b,
            ast.Or: lambda a, b: a or b,
            ast.Not: operator.not_,
            ast.In: lambda a, b: a in b,
            ast.NotIn: lambda a, b: a not in b,
            ast.Is: operator.is_,
            ast.IsNot: operator.is_not,
        }

        def _node(node: ast.AST) -> Any:
            if isinstance(node, ast.Expression):
                return _node(node.body)
            if isinstance(node, ast.Constant):
                return node.value
            if isinstance(node, ast.Name):
                return ctx.get(node.id)
            if isinstance(node, ast.BoolOp):
                values = [_node(v) for v in node.values]
                op = _OPS[type(node.op)]
                res = values[0]
                for v in values[1:]:
                    res = op(res, v)
                return res
            if isinstance(node, ast.UnaryOp):
                return _OPS[type(node.op)](_node(node.operand))
            if isinstance(node, ast.BinOp):
                return _OPS[type(node.op)](_node(node.left), _node(node.right))
            if isinstance(node, ast.Compare):
                left = _node(node.left)
                for op, comparator in zip(node.ops, node.comparators):
                    if not _OPS[type(op)](left, _node(comparator)):
                        return False
                    left = _node(comparator)
                return True
            if isinstance(node, ast.Attribute):
                obj = _node(node.value)
                return getattr(obj, node.attr, None)
            if isinstance(node, ast.Subscript):
                obj = _node(node.value)
                if isinstance(node.slice, ast.Constant):
                    return obj[node.slice.value]
                if isinstance(node.slice, ast.Index):  # py<3.9 compat
                    idx = _node(node.slice.value)
                    return obj[idx]
                idx = _node(node.slice)
                return obj[idx]
            if isinstance(node, ast.List):
                return [_node(e) for e in node.elts]
            if isinstance(node, ast.Tuple):
                return tuple(_node(e) for e in node.elts)
            if isinstance(node, ast.Dict):
                return {_node(k): _node(v) for k, v in zip(node.keys, node.values)}
            if isinstance(node, ast.Call):
                # 仅允许少量安全内置：len/str/int/float/bool
                fn = _node(node.func)
                allowed = {len, str, int, float, bool}
                if fn not in allowed:
                    raise ValueError(f"unsupported call: {fn}")
                args = [_node(a) for a in node.args]
                return fn(*args)
            if isinstance(node, ast.IfExp):
                return _node(node.body) if _node(node.test) else _node(node.orelse)
            raise ValueError(f"unsupported expression: {type(node).__name__}")


# 全局单例
condition_engine = ConditionEngine()
