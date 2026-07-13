"""
PRISM Agent - 代码格式化/重构
基于 AST 的自动代码美化
"""

from __future__ import annotations

import ast
import logging
from pathlib import Path
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


class CodeFormatter:
    def format(self, source: str) -> str:
        try:
            tree = ast.parse(source)
            return ast.unparse(tree)
        except Exception:
            return source

    def format_file(self, file_path: str) -> Dict[str, Any]:
        path = Path(file_path)
        if not path.exists():
            return {"success": False, "error": "file not found"}
        try:
            original = path.read_text(encoding="utf-8", errors="ignore")
            formatted = self.format(original)
            path.write_text(formatted, encoding="utf-8")
            return {"success": True, "path": str(path)}
        except Exception as exc:
            return {"success": False, "error": str(exc)}


code_formatter = CodeFormatter()
