"""
PRISM Agent - 代码迁移助手
框架/语言间代码迁移辅助
"""

from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)

_MIGRATE_DIR = Path.home() / ".prism" / "migrations"
_MIGRATE_DIR.mkdir(parents=True, exist_ok=True)


class CodeMigrationAssistant:
    def migrate(self, source_code: str, from_lang: str = "python", to_lang: str = "javascript") -> Dict[str, Any]:
        source_code = source_code or ""
        if not source_code.strip():
            return {"success": False, "error": "empty source"}
        if from_lang == "python" and to_lang == "javascript":
            return {"success": True, "code": self._py_to_js(source_code), "from": from_lang, "to": to_lang}
        if from_lang == "python" and to_lang == "typescript":
            return {"success": True, "code": self._py_to_js(source_code, typescript=True), "from": from_lang, "to": to_lang}
        return {"success": True, "code": source_code, "from": from_lang, "to": to_lang}

    def suggest_changes(self, source_code: str, from_lang: str = "python", to_lang: str = "javascript") -> List[Dict[str, Any]]:
        suggestions = []
        if from_lang == "python" and to_lang == "javascript":
            if "def " in source_code:
                suggestions.append({"from": "def func():", "to": "function func() {}", "reason": "python -> javascript 函数转换"})
            if "self" in source_code:
                suggestions.append({"from": "self", "to": "this", "reason": "python -> javascript 上下文转换"})
            if "import " in source_code:
                suggestions.append({"from": "import os", "to": "const os = require('os');", "reason": "python -> javascript 导入转换"})
        return suggestions

    def _py_to_js(self, source: str, typescript: bool = False) -> str:
        lines = source.splitlines()
        out = []
        for line in lines:
            stripped = line.strip()
            if stripped.startswith("def "):
                name = stripped[4:stripped.index("(")] if "(" in stripped else stripped[4:]
                params = stripped[stripped.index("(")+1:stripped.index(")")] if "(" in stripped and ")" in stripped else ""
                ret = ":" if "->" not in stripped else ":"
                out.append(f"function {name}({params}) {{")
                out.append("    // TODO: 迁移函数体")
                out.append("}")
            elif stripped.startswith("class "):
                name = stripped[6:].rstrip(":")
                out.append(f"class {name} {{")
                out.append("    constructor() {")
                out.append("        // TODO: 迁移构造函数")
                out.append("    }")
                out.append("}")
            elif stripped.startswith("import "):
                parts = stripped.split()
                if len(parts) >= 4 and parts[2] == "from":
                    module = parts[1]
                    package = parts[3].strip("\";")
                    out.append(f"const {module} = require('{package}');")
                else:
                    out.append(line)
            elif "self" in stripped:
                out.append(line.replace("self.", "this.").replace("self", "this"))
            else:
                out.append(line)
        return "\n".join(out)


code_migration_assistant = CodeMigrationAssistant()
