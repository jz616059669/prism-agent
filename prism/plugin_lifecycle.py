"""
PRISM Agent - 插件生命周期钩子
skill 执行前后注入逻辑，像 middleware
"""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional

logger = logging.getLogger(__name__)

_HOOK_DIR = Path.home() / ".prism" / "hooks"
_HOOK_DIR.mkdir(parents=True, exist_ok=True)


@dataclass
class Hook:
    name: str
    event: str = "before"  # before | after | error
    target: str = ""
    action: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return {
            "name": self.name,
            "event": self.event,
            "target": self.target,
            "action": self.action,
        }


class PluginLifecycleHooks:
    def __init__(self) -> None:
        self._hooks: Dict[str, List[Hook]] = {"before": [], "after": [], "error": []}
        self._load()

    def _load(self) -> None:
        for hook_file in _HOOK_DIR.glob("*.json"):
            try:
                data = json.loads(hook_file.read_text(encoding="utf-8"))
                hook = Hook(**data)
                self._hooks.setdefault(hook.event, []).append(hook)
            except Exception:
                continue

    def register(self, hook: Hook) -> Hook:
        self._hooks.setdefault(hook.event, []).append(hook)
        self._save(hook)
        return hook

    def execute(self, event: str, target: str, context: Dict[str, Any]) -> Dict[str, Any]:
        hooks = [h for h in self._hooks.get(event, []) if h.target in ("*", target)]
        ctx = dict(context)
        for hook in hooks:
            try:
                if hook.action == "log":
                    logger.info("hook %s %s %s", event, hook.name, target)
                elif hook.action == "abort":
                    ctx["aborted"] = True
                    ctx["abort_reason"] = hook.name
                    return ctx
                elif hook.action == "inject":
                    ctx.setdefault("injections", []).append(hook.name)
            except Exception:
                continue
        return ctx

    def list_hooks(self) -> List[Dict[str, Any]]:
        return [h.to_dict() for hooks in self._hooks.values() for h in hooks]

    def _save(self, hook: Hook) -> None:
        try:
            (_HOOK_DIR / f"{hook.name}.json").write_text(
                json.dumps(hook.to_dict(), ensure_ascii=False, indent=2),
                encoding="utf-8",
            )
        except Exception:
            pass


plugin_lifecycle_hooks = PluginLifecycleHooks()
