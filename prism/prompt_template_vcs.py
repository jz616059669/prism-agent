"""
PRISM Agent - Prompt 模板版本管理
模板变更记录 + diff + 回滚
"""

from __future__ import annotations

import difflib
import json
import logging
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)

_TMPL_DIR = Path.home() / ".prism" / "prompt_templates"
_TMPL_DIR.mkdir(parents=True, exist_ok=True)


@dataclass
class PromptTemplateVersion:
    name: str
    content: str = ""
    version: int = 1
    updated_at: float = field(default_factory=time.time)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "name": self.name,
            "content": self.content,
            "version": self.version,
            "updated_at": self.updated_at,
        }


class PromptTemplateVersionControl:
    def save(self, name: str, content: str) -> PromptTemplateVersion:
        template_file = _TMPL_DIR / f"{name}.jsonl"
        versions: List[Dict[str, Any]] = []
        if template_file.exists():
            try:
                versions = [json.loads(line) for line in template_file.read_text(encoding="utf-8").splitlines() if line.strip()]
            except Exception:
                pass
        last = versions[-1].get("version", 0) if versions else 0
        version = PromptTemplateVersion(name=name, content=content, version=last + 1, updated_at=time.time())
        try:
            with template_file.open("a", encoding="utf-8") as f:
                f.write(json.dumps(version.to_dict(), ensure_ascii=False) + "\n")
        except Exception:
            pass
        return version

    def history(self, name: str, limit: int = 50) -> List[Dict[str, Any]]:
        template_file = _TMPL_DIR / f"{name}.jsonl"
        if not template_file.exists():
            return []
        try:
            return [json.loads(line) for line in template_file.read_text(encoding="utf-8").splitlines() if line.strip()][-limit:]
        except Exception:
            return []

    def diff(self, name: str, from_version: int, to_version: int) -> str:
        history = self.history(name)
        from_item = next((v for v in history if v.get("version") == from_version), None)
        to_item = next((v for v in history if v.get("version") == to_version), None)
        if not from_item or not to_item:
            return ""
        from_lines = (from_item.get("content") or "").splitlines()
        to_lines = (to_item.get("content") or "").splitlines()
        diff = difflib.unified_diff(from_lines, to_lines, lineterm="")
        return "\n".join(list(diff)[:200])

    def rollback(self, name: str, version: int) -> bool:
        history = self.history(name)
        target = next((v for v in history if v.get("version") == version), None)
        if not target:
            return False
        return self.save(name, target.get("content", "")).version == version


prompt_template_vcs = PromptTemplateVersionControl()
