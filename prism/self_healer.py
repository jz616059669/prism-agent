"""
PRISM Agent - 自修复引擎
任务失败后自动回滚配置/代码，基于 task_feedback + profiler 记录的失败模式
"""

from __future__ import annotations

import json
import logging
import os
import subprocess
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)

_REPAIR_DIR = Path.home() / ".prism" / "repair"
_REPAIR_DIR.mkdir(parents=True, exist_ok=True)


@dataclass
class RepairAction:
    id: str
    action_type: str  # rollback_config | restart_service | clear_cache | downgrade_model
    target: str = ""
    applied_at: float = field(default_factory=time.time)
    success: bool = False
    error: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "action_type": self.action_type,
            "target": self.target,
            "applied_at": self.applied_at,
            "success": self.success,
            "error": self.error,
        }


class SelfHealer:
    def __init__(self) -> None:
        self._history: List[RepairAction] = []
        self._load_history()

    def _load_history(self) -> None:
        history_file = _REPAIR_DIR / "history.jsonl"
        if not history_file.exists():
            return
        try:
            for line in history_file.read_text(encoding="utf-8").splitlines():
                if not line.strip():
                    continue
                try:
                    data = json.loads(line)
                    self._history.append(RepairAction(**data))
                except Exception:
                    continue
        except Exception:
            pass

    def _save_action(self, action: RepairAction) -> None:
        try:
            with (_REPAIR_DIR / "history.jsonl").open("a", encoding="utf-8") as f:
                f.write(json.dumps(action.to_dict(), ensure_ascii=False) + "\n")
        except Exception:
            pass

    def diagnose(self, error_type: str, context: Dict[str, Any]) -> List[str]:
        suggestions: List[str] = []
        if "ModuleNotFoundError" in error_type:
            suggestions.append("restart_service")
            suggestions.append("clear_cache")
        elif "401" in error_type or "403" in error_type:
            suggestions.append("rollback_config")
        elif "timeout" in error_type.lower() or "timed out" in error_type.lower():
            suggestions.append("downgrade_model")
            suggestions.append("clear_cache")
        elif "rate_limit" in error_type.lower():
            suggestions.append("backoff")
        elif "connection" in error_type.lower():
            suggestions.append("restart_service")
        return suggestions

    def apply(self, action_type: str, target: str = "") -> RepairAction:
        action = RepairAction(id=f"{int(time.time())}_{action_type}", action_type=action_type, target=target)
        try:
            if action_type == "rollback_config":
                self._rollback_config(target)
            elif action_type == "restart_service":
                self._restart_service(target)
            elif action_type == "clear_cache":
                self._clear_cache()
            elif action_type == "downgrade_model":
                self._downgrade_model()
            elif action_type == "backoff":
                time.sleep(2.0)
            action.success = True
        except Exception as exc:
            action.error = str(exc)
            action.success = False
        self._history.append(action)
        self._save_action(action)
        return action

    def _rollback_config(self, target: str) -> None:
        if not target:
            return
        try:
            from prism.config import config as prism_config
            prism_config.revert(target)
        except Exception:
            pass

    def _restart_service(self, target: str) -> None:
        if target == "gateway":
            try:
                subprocess.run(["prism", "gateway", "restart"], capture_output=True, timeout=10)
            except Exception:
                pass
        elif target == "desktop":
            try:
                subprocess.run(["taskkill", "/F", "/IM", "python.exe"], capture_output=True, timeout=10)
            except Exception:
                pass

    def _clear_cache(self) -> None:
        cache_dir = Path.home() / ".prism" / "cache"
        try:
            if cache_dir.exists():
                for f in cache_dir.glob("*"):
                    try:
                        f.unlink()
                    except Exception:
                        pass
        except Exception:
            pass

    def _downgrade_model(self) -> None:
        try:
            from prism.config import config as prism_config
            current = prism_config.get("providers.stepfun.model", "")
            if "flash" in current:
                prism_config.set("providers.stepfun.model", "step-2-16k")
        except Exception:
            pass

    def history(self, limit: int = 20) -> List[Dict[str, Any]]:
        return [a.to_dict() for a in self._history[-limit:]]


self_healer = SelfHealer()
