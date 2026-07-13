"""
PRISM Agent - 交互式教程
内置引导教程，新用户上手
"""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)

_TUTORIAL_DIR = Path.home() / ".prism" / "tutorials"
_TUTORIAL_DIR.mkdir(parents=True, exist_ok=True)


@dataclass
class TutorialStep:
    title: str = ""
    content: str = ""
    action: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return {
            "title": self.title,
            "content": self.content,
            "action": self.action,
        }


@dataclass
class Tutorial:
    id: str
    name: str = ""
    steps: List[TutorialStep] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "name": self.name,
            "steps": [s.to_dict() for s in self.steps],
        }


class TutorialManager:
    def __init__(self) -> None:
        self._tutorials: Dict[str, Tutorial] = {}
        self._progress: Dict[str, int] = {}
        self._load_builtins()
        self._load()

    def _load_builtins(self) -> None:
        quickstart = Tutorial(
            id="quickstart",
            name="快速开始",
            steps=[
                TutorialStep(title="欢迎", content="欢迎使用 PRISM Agent。", action="next"),
                TutorialStep(title="对话", content="在输入框输入消息开始对话。", action="next"),
                TutorialStep(title="技能", content="在左侧技能面板浏览可用技能。", action="finish"),
            ],
        )
        self._tutorials["quickstart"] = quickstart

    def _load(self) -> None:
        progress_file = _TUTORIAL_DIR / "progress.json"
        if progress_file.exists():
            try:
                self._progress = json.loads(progress_file.read_text(encoding="utf-8"))
            except Exception:
                pass

    def start(self, tutorial_id: str) -> Optional[Dict[str, Any]]:
        tutorial = self._tutorials.get(tutorial_id)
        if not tutorial:
            return None
        self._progress[tutorial_id] = 0
        self._save_progress()
        return tutorial.to_dict()

    def next_step(self, tutorial_id: str) -> Optional[Dict[str, Any]]:
        tutorial = self._tutorials.get(tutorial_id)
        if not tutorial:
            return None
        idx = self._progress.get(tutorial_id, 0)
        if idx + 1 < len(tutorial.steps):
            self._progress[tutorial_id] = idx + 1
            self._save_progress()
            return tutorial.steps[idx + 1].to_dict()
        return {"status": "completed"}

    def current_step(self, tutorial_id: str) -> Optional[Dict[str, Any]]:
        tutorial = self._tutorials.get(tutorial_id)
        if not tutorial:
            return None
        idx = self._progress.get(tutorial_id, 0)
        if idx < len(tutorial.steps):
            return tutorial.steps[idx].to_dict()
        return {"status": "completed"}

    def _save_progress(self) -> None:
        try:
            (_TUTORIAL_DIR / "progress.json").write_text(
                json.dumps(self._progress, ensure_ascii=False, indent=2),
                encoding="utf-8",
            )
        except Exception:
            pass


tutorial_manager = TutorialManager()
