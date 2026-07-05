"""
PRISM Agent - Hooks System
借鉴 Codex CLI 的 hooks 机制，在关键节点注入自定义逻辑。
"""

from __future__ import annotations

import ast
import fnmatch
import logging
import operator
from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List, Optional

logger = logging.getLogger("prism.hooks")


@dataclass
class Hook:
    name: str
    event: str
    pattern: str = "*"
    action: str = "run"  # run | block
    command: str = ""
    timeout: int = 30
    enabled: bool = True


@dataclass
class HookResult:
    hook: Hook
    passed: bool
    output: str = ""
    error: Optional[str] = None


class _SafeExprEvaluator:
    """受限表达式求值器：仅支持安全子集，避免 eval 执行任意代码。"""

    _SAFE_NAMES = {
        "True": True,
        "False": False,
        "None": None,
    }
    _SAFE_OPS = {
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
        ast.And: ...,
        ast.Or: ...,
        ast.Not: operator.not_,
        ast.In: lambda a, b: a in b,
        ast.NotIn: lambda a, b: a not in b,
        ast.Is: operator.is_,
        ast.IsNot: operator.is_not,
    }

    def __init__(self, context: Dict[str, Any]):
        self._context = context

    def _eval(self, node: ast.AST) -> Any:
        if isinstance(node, ast.Expression):
            return self._eval(node.body)
        if isinstance(node, ast.Constant):
            return node.value
        if isinstance(node, ast.Name):
            if node.id in self._SAFE_NAMES:
                return self._SAFE_NAMES[node.id]
            if node.id in self._context:
                return self._context[node.id]
            raise ValueError(f"block hook 不允许的变量: {node.id}")
        if isinstance(node, ast.Attribute):
            value = self._eval(node.value)
            return getattr(value, node.attr)
        if isinstance(node, ast.Subscript):
            value = self._eval(node.value)
            if isinstance(node.slice, ast.Constant):
                key = node.slice.value
            else:
                key = self._eval(node.slice)
            return value[key]
        if isinstance(node, ast.List):
            return [self._eval(el) for el in node.elts]
        if isinstance(node, ast.Tuple):
            return tuple(self._eval(el) for el in node.elts)
        if isinstance(node, ast.Dict):
            return {self._eval(k): self._eval(v) for k, v in zip(node.keys, node.values)}
        if isinstance(node, ast.BoolOp):
            if isinstance(node.op, ast.And):
                result = True
                for value in node.values:
                    result = self._eval(value)
                    if not result:
                        return result
                return result
            if isinstance(node.op, ast.Or):
                result = False
                for value in node.values:
                    result = self._eval(value)
                    if result:
                        return result
                return result
            raise ValueError("不支持的布尔运算符")
        if isinstance(node, ast.UnaryOp) and isinstance(node.op, ast.Not):
            return not self._eval(node.operand)
        if isinstance(node, ast.Compare):
            left = self._eval(node.left)
            for op, comparator in zip(node.ops, node.comparators):
                right = self._eval(comparator)
                op_func = self._SAFE_OPS.get(type(op))
                if op_func is None:
                    raise ValueError(f"block hook 不允许的比较运算符: {type(op).__name__}")
                if not op_func(left, right):
                    return False
                left = right
            return True
        if isinstance(node, ast.BinOp):
            left = self._eval(node.left)
            right = self._eval(node.right)
            op_func = self._SAFE_OPS.get(type(node.op))
            if op_func is None:
                raise ValueError(f"block hook 不允许的二元运算符: {type(node.op).__name__}")
            return op_func(left, right)
        if isinstance(node, ast.Call):
            func = self._eval(node.func)
            args = [self._eval(arg) for arg in node.args]
            kwargs = {kw.arg: self._eval(kw.value) for kw in node.keywords}
            if not callable(func):
                raise ValueError("block hook 只允许调用上下文对象的方法/函数")
            return func(*args, **kwargs)
        raise ValueError(f"block hook 不允许的表达式类型: {type(node).__name__}")

    def evaluate(self, command: str) -> bool:
        try:
            tree = ast.parse(command, mode="eval")
        except SyntaxError as exc:
            raise ValueError(f"block hook 语法错误: {exc}") from exc
        return bool(self._eval(tree))


class HookManager:
    """管理 hooks 的注册、匹配和执行。"""

    SUPPORTED_EVENTS = {
        "before_chat",
        "after_chat",
        "before_tool",
        "after_tool",
        "before_file_write",
        "after_file_write",
        "before_command",
        "after_command",
        "on_error",
        "on_session_save",
        "on_session_load",
    }

    def __init__(self) -> None:
        self._hooks: List[Hook] = []
        self._results: List[HookResult] = []

    def register(self, hook: Hook) -> None:
        if hook.event not in self.SUPPORTED_EVENTS:
            raise ValueError(f"Unsupported hook event: {hook.event}")
        self._hooks.append(hook)
        logger.debug("hook registered: %s -> %s", hook.event, hook.name)

    def unregister(self, name: str) -> None:
        self._hooks = [h for h in self._hooks if h.name != name]

    def get_hooks(self, event: str, pattern: str = "*") -> List[Hook]:
        matched = []
        for hook in self._hooks:
            if not hook.enabled:
                continue
            if hook.event != event:
                continue
            if not fnmatch.fnmatch(pattern, hook.pattern):
                continue
            matched.append(hook)
        return matched

    def run_hooks(self, event: str, context: Dict[str, Any]) -> HookResult:
        pattern = context.get("pattern", "*")
        hooks = self.get_hooks(event, pattern)
        if not hooks:
            return HookResult(hook=Hook("", event), passed=True)

        last_result = HookResult(hook=Hook("", event), passed=True)
        for hook in hooks:
            try:
                if hook.action == "run":
                    import subprocess
                    result = subprocess.run(
                        hook.command,
                        shell=True,
                        capture_output=True,
                        text=True,
                        timeout=hook.timeout,
                        env={},
                    )
                    output = (result.stdout or result.stderr or "").strip()
                    passed = result.returncode == 0
                    last_result = HookResult(
                        hook=hook,
                        passed=passed,
                        output=output,
                        error=None if passed else f"exit {result.returncode}",
                    )
                    if not passed:
                        logger.warning("hook %s failed: %s", hook.name, last_result.error)
                        break
                else:
                    evaluator = _SafeExprEvaluator(context)
                    passed = evaluator.evaluate(hook.command)
                    last_result = HookResult(hook=hook, passed=bool(passed))
                    if not passed:
                        logger.warning("hook %s blocked", hook.name)
                        break
            except subprocess.TimeoutExpired:
                last_result = HookResult(hook=hook, passed=False, error="timeout")
                break
            except Exception as exc:
                last_result = HookResult(hook=hook, passed=False, error=str(exc))
                break
        return last_result

    def load_from_config(self, config: Dict[str, Any]) -> None:
        hooks_cfg = config.get("hooks", [])
        for h in hooks_cfg:
            try:
                hook = Hook(
                    name=h.get("name", ""),
                    event=h.get("event", ""),
                    pattern=h.get("pattern", "*"),
                    action=h.get("action", "run"),
                    command=h.get("command", ""),
                    timeout=int(h.get("timeout", 30)),
                )
                if hook.name and hook.event:
                    self.register(hook)
            except Exception as exc:
                logger.warning("invalid hook config: %s", exc)


# 全局 hooks 管理器实例
hook_manager = HookManager()
