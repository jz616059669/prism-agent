"""
PRISM Agent - 代码差异高亮
智能 diff，语义级高亮
"""

from __future__ import annotations

import difflib
import json
import logging
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


@dataclass
class DiffLine:
    kind: str = "context"  # context | add | remove
    old_no: int = 0
    new_no: int = 0
    content: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return {
            "kind": self.kind,
            "old_no": self.old_no,
            "new_no": self.new_no,
            "content": self.content,
        }


class CodeDiffHighlighter:
    def diff(self, old_text: str, new_text: str) -> List[DiffLine]:
        old_lines = (old_text or "").splitlines()
        new_lines = (new_text or "").splitlines()
        result: List[DiffLine] = []
        diff = difflib.unified_diff(old_lines, new_lines, lineterm="")
        old_no = 0
        new_no = 0
        for line in diff:
            kind = "context"
            if line.startswith("---") or line.startswith("+++"):
                continue
            if line.startswith("@@"):
                try:
                    parts = line.split("@@")
                    if len(parts) >= 3:
                        nums = parts[1].strip().split(" ")
                        old_no = int(nums[0].split(",")[0].lstrip("-"))
                        new_no = int(nums[1].split(",")[0].lstrip("-"))
                except Exception:
                    pass
                continue
            if line.startswith("-"):
                kind = "remove"
                old_no += 1
            elif line.startswith("+"):
                kind = "add"
                new_no += 1
            else:
                old_no += 1
                new_no += 1
            result.append(DiffLine(kind=kind, old_no=old_no if kind == "remove" else old_no, new_no=new_no if kind == "add" else new_no, content=line))
        return result

    def to_html(self, diff_lines: List[DiffLine]) -> str:
        colors = {"remove": "#ff4d4d", "add": "#4dff4d", "context": "#ffffff"}
        rows = []
        for line in diff_lines:
            color = colors.get(line.kind, "#ffffff")
            content = line.content.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
            rows.append(f"<tr style='background:{color}'><td style='color:#888'>{line.old_no}</td><td style='color:#888'>{line.new_no}</td><td style='font-family:monospace'>{content}</td></tr>")
        return f"<table style='width:100%;border-collapse:collapse'>{''.join(rows)}</table>"


code_diff_highlighter = CodeDiffHighlighter()
