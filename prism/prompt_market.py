"""
PRISM Agent - 提示模板市场
reuse prompt 模板，内置 + 导入
"""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)

_PROMPT_DIR = Path.home() / ".prism" / "prompts"
_PROMPT_DIR.mkdir(parents=True, exist_ok=True)


@dataclass
class PromptTemplate:
    name: str
    template: str = ""
    tags: List[str] = field(default_factory=list)
    description: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return {
            "name": self.name,
            "template": self.template,
            "tags": list(self.tags),
            "description": self.description,
        }


class PromptMarket:
    def __init__(self) -> None:
        self._templates: Dict[str, PromptTemplate] = {}
        self._load()

    def _load(self) -> None:
        for prompt_file in _PROMPT_DIR.glob("*.json"):
            try:
                data = json.loads(prompt_file.read_text(encoding="utf-8"))
                template = PromptTemplate(**data)
                self._templates[template.name] = template
            except Exception:
                continue

    def add(self, template: PromptTemplate) -> PromptTemplate:
        self._templates[template.name] = template
        self._save(template)
        return template

    def get(self, name: str) -> Optional[PromptTemplate]:
        return self._templates.get(name)

    def list_templates(self) -> List[Dict[str, Any]]:
        return [t.to_dict() for t in self._templates.values()]

    def render(self, name: str, variables: Optional[Dict[str, str]] = None) -> Optional[str]:
        template = self._templates.get(name)
        if not template:
            return None
        text = template.template
        if variables:
            for key, value in (variables or {}).items():
                text = text.replace("{" + key + "}", str(value))
        return text

    def _save(self, template: PromptTemplate) -> None:
        try:
            (_PROMPT_DIR / f"{template.name}.json").write_text(
                json.dumps(template.to_dict(), ensure_ascii=False, indent=2),
                encoding="utf-8",
            )
        except Exception:
            pass


prompt_market = PromptMarket()
