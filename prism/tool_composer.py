"""
PRISM Agent - Tool Composer
动态组合工具成新工具，像搭积木
"""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)

_COMPOSER_DIR = Path.home() / ".prism" / "composer"
_COMPOSER_DIR.mkdir(parents=True, exist_ok=True)


@dataclass
class ComposedTool:
    name: str
    steps: List[Dict[str, Any]] = field(default_factory=list)
    description: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return {
            "name": self.name,
            "steps": list(self.steps),
            "description": self.description,
        }


class ToolComposer:
    def __init__(self) -> None:
        self._tools: Dict[str, ComposedTool] = {}
        self._load()

    def _load(self) -> None:
        for tool_file in _COMPOSER_DIR.glob("*.json"):
            try:
                data = json.loads(tool_file.read_text(encoding="utf-8"))
                tool = ComposedTool(**data)
                self._tools[tool.name] = tool
            except Exception:
                continue

    def compose(self, tool: ComposedTool) -> ComposedTool:
        self._tools[tool.name] = tool
        try:
            (_COMPOSER_DIR / f"{tool.name}.json").write_text(
                json.dumps(tool.to_dict(), ensure_ascii=False, indent=2),
                encoding="utf-8",
            )
        except Exception:
            pass
        return tool

    def get(self, name: str) -> Optional[ComposedTool]:
        return self._tools.get(name)

    def list_tools(self) -> List[Dict[str, Any]]:
        return [t.to_dict() for t in self._tools.values()]

    def run(self, name: str, context: Dict[str, Any]) -> Dict[str, Any]:
        tool = self._tools.get(name)
        if not tool:
            return {"success": False, "error": f"composed tool not found: {name}"}
        outputs: Dict[str, Any] = {}
        for step in tool.steps:
            action = step.get("action", "")
            if action == "echo":
                outputs[step.get("name", "step")] = step.get("value", "")
            elif action == "sum":
                values = [float(v) for v in step.get("values", [])]
                outputs[step.get("name", "step")] = sum(values)
            elif action == "format":
                template = step.get("template", "{input}")
                outputs[step.get("name", "step")] = template.format(**context)
            else:
                outputs[step.get("name", "step")] = ""
        return {"success": True, "tool": name, "outputs": outputs}


tool_composer = ToolComposer()
