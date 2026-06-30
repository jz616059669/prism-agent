"""
PRISM Agent - Hooks System
借鉴 Codex CLI 的 hooks 机制，在关键节点注入自定义逻辑。
"""

from __future__ import annotations

import fnmatch
import logging
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
                    # block 类型：command 作为 Python 表达式求值
                    passed = eval(hook.command, {"ctx": context})  # noqa: S307
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
