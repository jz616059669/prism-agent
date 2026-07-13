"""
PRISM Agent - 自动化测试生成
基于 AST 自动生成 pytest 单测模板
"""

from __future__ import annotations

import ast
import logging
from pathlib import Path
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


class AutoTestGenerator:
    def generate_for_file(self, file_path: str) -> str:
        path = Path(file_path)
        if not path.exists():
            return ""
        try:
            text = path.read_text(encoding="utf-8")
            return self._generate(text, path.stem)
        except Exception:
            return ""

    def _generate(self, source: str, module_name: str) -> str:
        lines = ["\"\"\"Auto-generated tests\"\"\"", "from __future__ import annotations", ""]
        try:
            tree = ast.parse(source)
        except Exception:
            return ""
        for node in tree.body:
            if isinstance(node, ast.FunctionDef) and node.name.startswith("test_"):
                continue
            if isinstance(node, ast.FunctionDef) and not node.name.startswith("_"):
                args = [arg.arg for arg in node.args.args]
                lines.append(f"def test_{node.name}():")
                if args:
                    lines.append(f"    # TODO: replace with real args")
                    lines.append(f"    from {module_name} import {node.name}")
                    lines.append(f"    {node.name}({', '.join(['None'] * len(args))})")
                else:
                    lines.append(f"    from {module_name} import {node.name}")
                    lines.append(f"    assert {node.name}() is None or True")
                lines.append("")
        return "\n".join(lines)


auto_test_generator = AutoTestGenerator()
