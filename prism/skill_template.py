"""
PRISM Agent - 技能组合/工作流模板
预设技能包一键启用，如“写作包”“编码包”
"""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)

_TEMPLATE_DIR = Path.home() / ".prism" / "skill_templates"
_TEMPLATE_DIR.mkdir(parents=True, exist_ok=True)


@dataclass
class SkillTemplate:
    name: str
    description: str = ""
    skills: List[str] = field(default_factory=list)
    personas: List[str] = field(default_factory=list)
    workflows: List[str] = field(default_factory=list)
    tags: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "name": self.name,
            "description": self.description,
            "skills": list(self.skills),
            "personas": list(self.personas),
            "workflows": list(self.workflows),
            "tags": list(self.tags),
        }


class SkillTemplateStore:
    def __init__(self) -> None:
        self._templates: Dict[str, SkillTemplate] = {}
        self._active: set = set()
        self._load()

    def _load(self) -> None:
        for template_file in _TEMPLATE_DIR.glob("*.json"):
            try:
                data = json.loads(template_file.read_text(encoding="utf-8"))
                template = SkillTemplate(**data)
                self._templates[template.name] = template
            except Exception:
                continue

    def add(self, template: SkillTemplate) -> SkillTemplate:
        self._templates[template.name] = template
        self._save(template)
        return template

    def get(self, name: str) -> Optional[SkillTemplate]:
        return self._templates.get(name)

    def list_templates(self) -> List[Dict[str, Any]]:
        return [t.to_dict() for t in self._templates.values()]

    def activate(self, name: str) -> Dict[str, Any]:
        template = self._templates.get(name)
        if not template:
            return {"success": False, "error": "template not found"}
        self._active.add(name)
        try:
            from prism.skills import load_external_skills
            load_external_skills(names=template.skills)
        except Exception as exc:
            return {"success": False, "error": str(exc)}
        return {"success": True, "template": template.to_dict()}

    def deactivate(self, name: str) -> Dict[str, Any]:
        if name not in self._active:
            return {"success": False, "error": "not active"}
        self._active.discard(name)
        return {"success": True}

    def active(self) -> List[str]:
        return sorted(self._active)

    def _save(self, template: SkillTemplate) -> None:
        try:
            (_TEMPLATE_DIR / f"{template.name}.json").write_text(
                json.dumps(template.to_dict(), ensure_ascii=False, indent=2),
                encoding="utf-8",
            )
        except Exception:
            pass


skill_template_store = SkillTemplateStore()
