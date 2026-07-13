"""
PRISM Agent - 智能补全
上下文感知的代码/文本补全
"""

from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)

_COMPLETE_DIR = Path.home() / ".prism" / "completions"
_COMPLETE_DIR.mkdir(parents=True, exist_ok=True)


class SmartCompleter:
    def complete(self, prefix: str, context: str = "", limit: int = 10) -> List[str]:
        prefix = prefix or ""
        ctx = (context or "").lower()
        candidates: List[str] = []
        if "def " in ctx:
            candidates.append("def main():\n    pass")
        if "class " in ctx:
            candidates.append("class Foo:\n    pass")
        if "import " in ctx or prefix == "import":
            candidates.extend(["import os", "import sys", "import json"])
        if "print" in prefix:
            candidates.append("print(f'{value}')")
        if "for " in ctx:
            candidates.append("for item in items:\n    pass")
        if "try" in ctx:
            candidates.append("try:\n    pass\nexcept Exception:\n    pass")
        if not candidates:
            candidates = [prefix + " ", prefix + "()", prefix + " = "]
        return candidates[:limit]

    def complete_code(self, code: str, language: str = "python") -> List[str]:
        return self.complete(prefix=code.splitlines()[-1] if code else "", context=code, limit=10)


smart_completer = SmartCompleter()
