"""
PRISM Agent - 自然语言生成代码
描述需求直接生成可运行代码
"""

from __future__ import annotations

import logging
import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, Optional

logger = logging.getLogger(__name__)

_GEN_DIR = Path.home() / ".prism" / "generated"
_GEN_DIR.mkdir(parents=True, exist_ok=True)


@dataclass
class GeneratedCode:
    name: str
    language: str = "python"
    code: str = ""
    path: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return {
            "name": self.name,
            "language": self.language,
            "code": self.code,
            "path": self.path,
        }


class NaturalLanguageCodeGenerator:
    def generate(self, description: str, language: str = "python") -> GeneratedCode:
        description = (description or "").strip()
        if not description:
            return GeneratedCode(name="empty", code="", path="")
        name = description[:24].replace(" ", "_").replace("/", "_")
        if language == "python":
            code = self._generate_python(description)
        else:
            code = f"# {description}\n"
        path = str(_GEN_DIR / f"{name}.py")
        try:
            Path(path).write_text(code, encoding="utf-8")
        except Exception:
            path = ""
        return GeneratedCode(name=name, language=language, code=code, path=path)

    def _generate_python(self, description: str) -> str:
        desc = description.replace('"', '\\"')
        return '"""\n' + desc + '\n"""\n\ndef main():\n    print("hello from PRISM generated code")\n\n\nif __name__ == "__main__":\n    main()\n'


natural_language_code_generator = NaturalLanguageCodeGenerator()
