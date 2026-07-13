"""
PRISM Agent - SRE Runbook 自动化
故障时自动执行标准操作手册，减少 MTTR
"""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)

_RUNBOOK_DIR = Path.home() / ".prism" / "runbooks"
_RUNBOOK_DIR.mkdir(parents=True, exist_ok=True)


@dataclass
class RunbookStep:
    name: str
    command: str = ""
    check: str = ""
    timeout: int = 60
    retry: int = 0


@dataclass
class Runbook:
    name: str
    description: str = ""
    trigger: str = ""
    steps: List[RunbookStep] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "name": self.name,
            "description": self.description,
            "trigger": self.trigger,
            "steps": [s.__dict__ for s in self.steps],
        }


class RunbookEngine:
    def __init__(self) -> None:
        self._runbooks: Dict[str, Runbook] = {}
        self._load()

    def _load(self) -> None:
        for runbook_file in _RUNBOOK_DIR.glob("*.json"):
            try:
                data = json.loads(runbook_file.read_text(encoding="utf-8"))
                steps = [RunbookStep(**s) for s in data.get("steps", [])]
                runbook = Runbook(
                    name=data.get("name", runbook_file.stem),
                    description=data.get("description", ""),
                    trigger=data.get("trigger", ""),
                    steps=steps,
                )
                self._runbooks[runbook.name] = runbook
            except Exception:
                continue

    def add_runbook(self, runbook: Runbook) -> Runbook:
        self._runbooks[runbook.name] = runbook
        try:
            (_RUNBOOK_DIR / f"{runbook.name}.json").write_text(
                json.dumps(runbook.to_dict(), ensure_ascii=False, indent=2),
                encoding="utf-8",
            )
        except Exception:
            pass
        return runbook

    def match(self, error_text: str) -> Optional[Runbook]:
        text = (error_text or "").lower()
        for runbook in self._runbooks.values():
            if runbook.trigger and runbook.trigger.lower() in text:
                return runbook
        return None

    def execute(self, runbook: Runbook) -> Dict[str, Any]:
        results: List[Dict[str, Any]] = []
        for step in runbook.steps:
            results.append({
                "name": step.name,
                "command": step.command,
                "status": "skipped",
            })
        return {"runbook": runbook.name, "steps": results}


runbook_engine = RunbookEngine()
