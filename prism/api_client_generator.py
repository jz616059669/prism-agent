"""
PRISM Agent - API 客户端生成
从 OpenAPI spec 生成客户端代码
"""

from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)

_GEN_DIR = Path.home() / ".prism" / "generated"
_GEN_DIR.mkdir(parents=True, exist_ok=True)


class ApiClientGenerator:
    def generate(self, spec: Dict[str, Any], language: str = "python") -> Dict[str, Any]:
        title = spec.get("info", {}).get("title", "api")
        safe = title.replace(" ", "_").replace("-", "_")
        if language == "python":
            code = self._generate_python(safe, spec)
        elif language == "javascript":
            code = self._generate_javascript(safe, spec)
        else:
            code = "// unsupported language"
        path = str(_GEN_DIR / f"{safe}_client.{language == 'python' and 'py' or 'js'}")
        try:
            Path(path).write_text(code, encoding="utf-8")
        except Exception:
            pass
        return {"success": True, "path": path, "language": language, "code": code}

    def _generate_python(self, name: str, spec: Dict[str, Any]) -> str:
        base = spec.get("servers", [{}])[0].get("url", "https://api.example.com")
        paths = spec.get("paths", {})
        methods = []
        for path, methods_map in paths.items():
            for method in methods_map.keys():
                func = path.strip("/").replace("/", "_").replace("{", "").replace("}", "")
                methods.append(f"    def {method}_{func}(self, **kwargs):\n        return self._request('{method.upper()}', '{path}', **kwargs)\n")
        return f'"""Generated {name} client"""\n\nimport requests\n\n\nclass {name.title()}Client:\n    def __init__(self, base_url: str = "{base}"):\n        self.base_url = base_url.rstrip("/")\n\n    def _request(self, method: str, path: str, **kwargs):\n        url = self.base_url + path\n        return requests.request(method, url, **kwargs)\n\n' + "\n".join(methods)

    def _generate_javascript(self, name: str, spec: Dict[str, Any]) -> str:
        base = spec.get("servers", [{}])[0].get("url", "https://api.example.com")
        return f'// Generated {name} client\n\nclass {name.title()}Client {{\n  constructor(baseUrl = "{base}") {{\n    this.baseUrl = baseUrl.replace(/\\/$/, "");\n  }}\n\n  async request(method, path, options = {{}}) {{\n    const url = this.baseUrl + path;\n    const res = await fetch(url, {{ method, ...options }});\n    return res.json();\n  }}\n}}\n\nexport default {name.title()}Client;\n'


api_client_generator = ApiClientGenerator()
