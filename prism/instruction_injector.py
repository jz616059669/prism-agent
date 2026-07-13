"""
PRISM Agent - 自定义指令注入
用户全局指令，自动注入每次对话
"""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)

_INJECT_DIR = Path.home() / ".prism" / "inject"
_INJECT_DIR.mkdir(parents=True, exist_ok=True)


@dataclass
class CustomInstruction:
    id: str
    text: str = ""
    enabled: bool = True
    priority: int = 0

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "text": self.text,
            "enabled": self.enabled,
            "priority": self.priority,
        }


class InstructionInjector:
    def __init__(self) -> None:
        self._instructions: List[CustomInstruction] = []
        self._load()

    def _load(self) -> None:
        for instruction_file in _INJECT_DIR.glob("*.json"):
            try:
                data = json.loads(instruction_file.read_text(encoding="utf-8"))
                self._instructions.append(CustomInstruction(**data))
            except Exception:
                continue
        self._instructions.sort(key=lambda x: x.priority, reverse=True)

    def add(self, instruction: CustomInstruction) -> CustomInstruction:
        self._instructions.append(instruction)
        self._instructions.sort(key=lambda x: x.priority, reverse=True)
        self._save(instruction)
        return instruction

    def remove(self, instruction_id: str) -> bool:
        self._instructions = [i for i in self._instructions if i.id != instruction_id]
        try:
            (_INJECT_DIR / f"{instruction_id}.json").unlink()
        except Exception:
            pass
        return True

    def inject(self, user_message: str) -> str:
        parts = [i.text for i in self._instructions if i.enabled and i.text]
        if not parts:
            return user_message
        prefix = "\n".join(parts)
        return f"{prefix}\n{user_message}"

    def list_instructions(self) -> List[Dict[str, Any]]:
        return [i.to_dict() for i in self._instructions]

    def _save(self, instruction: CustomInstruction) -> None:
        try:
            (_INJECT_DIR / f"{instruction.id}.json").write_text(
                json.dumps(instruction.to_dict(), ensure_ascii=False, indent=2),
                encoding="utf-8",
            )
        except Exception:
            pass


instruction_injector = InstructionInjector()
