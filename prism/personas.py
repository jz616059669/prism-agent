"""
PRISM Agent - Persona 角色人格系统
一键切换系统提示词 + 记忆隔离
"""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)

_PERSONA_DIR = Path.home() / ".prism" / "personas"
_PERSONA_DIR.mkdir(parents=True, exist_ok=True)


@dataclass
class Persona:
    name: str
    description: str = ""
    system_prompt: str = ""
    tags: List[str] = field(default_factory=list)
    memory_scope: str = "default"  # 隔离维度：default / novel / code / translate
    active: bool = False

    def to_dict(self) -> Dict[str, Any]:
        return {
            "name": self.name,
            "description": self.description,
            "system_prompt": self.system_prompt,
            "tags": self.tags,
            "memory_scope": self.memory_scope,
            "active": self.active,
        }


class PersonaManager:
    def __init__(self) -> None:
        self._personas: Dict[str, Persona] = {}
        self._load_builtin()

    def _load_builtin(self):
        builtins = [
            Persona(
                name="默认",
                description="默认助手",
                system_prompt="你是 PRISM Agent 默认助手，帮助用户完成任务。",
                tags=["默认"],
                active=True,
            ),
            Persona(
                name="网文创作",
                description="网文创作模式",
                system_prompt="你是资深网文创作助手，擅长爽文节奏、人物塑造、对话张力。保持轻松幽默的叙事风格。",
                tags=["创作", "网文", "小说"],
                memory_scope="novel",
            ),
            Persona(
                name="编程专家",
                description="编程专家模式",
                system_prompt="你是资深全栈工程师，擅长 Python/TypeScript/系统架构。给出可运行、可测试、带错误处理的代码。",
                tags=["代码", "编程", "debug"],
                memory_scope="code",
            ),
            Persona(
                name="中英翻译",
                description="中英翻译模式",
                system_prompt="你是专业中英翻译，忠实原文风格，保留文化 nuance。需要专业术语时给出原文对照。",
                tags=["翻译", "英文", "中文"],
                memory_scope="translate",
            ),
        ]
        for p in builtins:
            self._personas[p.name] = p

    def list_personas(self) -> List[Dict[str, Any]]:
        return [p.to_dict() for p in self._personas.values()]

    def get(self, name: str) -> Optional[Persona]:
        return self._personas.get(name)

    def activate(self, name: str) -> Optional[Persona]:
        persona = self._personas.get(name)
        if not persona:
            return None
        for p in self._personas.values():
            p.active = False
        persona.active = True
        return persona

    def create(self, persona: Persona) -> Persona:
        self._personas[persona.name] = persona
        return persona

    def delete(self, name: str) -> bool:
        if name in self._personas:
            del self._personas[name]
            return True
        return False


persona_manager = PersonaManager()
