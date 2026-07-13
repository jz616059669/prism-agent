"""
PRISM Agent - 对话模板
常见场景预设模板，一键启用
"""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)

_TMPL_DIR = Path.home() / ".prism" / "conversation_templates"
_TMPL_DIR.mkdir(parents=True, exist_ok=True)


@dataclass
class ConversationTemplate:
    id: str
    name: str = ""
    system_prompt: str = ""
    first_message: str = ""
    variables: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "name": self.name,
            "system_prompt": self.system_prompt,
            "first_message": self.first_message,
            "variables": list(self.variables),
        }


class ConversationTemplateStore:
    def __init__(self) -> None:
        self._templates: Dict[str, ConversationTemplate] = {}
        self._load_builtins()
        self._load()

    def _load_builtins(self) -> None:
        self._templates["blank"] = ConversationTemplate(id="blank", name="空白对话", system_prompt="", first_message="", variables=[])
        self._templates["coding"] = ConversationTemplate(id="coding", name="编码助手", system_prompt="你是一个专业的编程助手。", first_message="请告诉我你要写什么代码。", variables=["language", "framework"])

    def _load(self) -> None:
        for template_file in _TMPL_DIR.glob("*.json"):
            try:
                data = json.loads(template_file.read_text(encoding="utf-8"))
                template = ConversationTemplate(**data)
                self._templates[template.id] = template
            except Exception:
                continue

    def get(self, template_id: str) -> Optional[ConversationTemplate]:
        return self._templates.get(template_id)

    def list_templates(self) -> List[Dict[str, Any]]:
        return [t.to_dict() for t in self._templates.values()]

    def render(self, template_id: str, variables: Optional[Dict[str, str]] = None) -> Dict[str, Any]:
        template = self._templates.get(template_id)
        if not template:
            return {"success": False, "error": f"template not found: {template_id}"}
        variables = variables or {}
        try:
            system_prompt = template.system_prompt.format(**variables)
            first_message = template.first_message.format(**variables)
        except Exception as exc:
            return {"success": False, "error": str(exc)}
        return {"success": True, "system_prompt": system_prompt, "first_message": first_message}


conversation_template_store = ConversationTemplateStore()
