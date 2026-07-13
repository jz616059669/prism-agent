"""
PRISM Agent - 插件依赖自动解析
安装 skill 时自动安装依赖，处理版本冲突
"""

from __future__ import annotations

import logging
import subprocess
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


@dataclass
class DependencyResult:
    name: str
    version: str = ""
    installed: bool = False
    conflict: bool = False
    error: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return {
            "name": self.name,
            "version": self.version,
            "installed": self.installed,
            "conflict": self.conflict,
            "error": self.error,
        }


class DependencyResolver:
    def __init__(self, venv_python: Optional[str] = None) -> None:
        self.venv_python = venv_python or Path.home() / ".prism" / "venv" / "bin" / "python"

    def resolve(self, dependencies: List[Dict[str, str]]) -> List[DependencyResult]:
        results: List[DependencyResult] = []
        for dep in dependencies:
            name = dep.get("name", "")
            version = dep.get("version", "")
            results.append(self._install(name, version))
        return results

    def _install(self, name: str, version: str) -> DependencyResult:
        result = DependencyResult(name=name, version=version)
        if not name:
            result.error = "empty name"
            return result
        try:
            pip_args = ["pip", "install", f"{name}{version}"]
            proc = subprocess.run(pip_args, capture_output=True, text=True, timeout=120)
            if proc.returncode == 0:
                result.installed = True
            else:
                result.conflict = "already satisfied" in proc.stdout.lower() or "conflict" in proc.stderr.lower()
                result.error = proc.stderr or proc.stdout
        except Exception as exc:
            result.error = str(exc)
        return result

    def resolve_from_skill(self, skill_path: str) -> List[DependencyResult]:
        results: List[DependencyResult] = []
        try:
            text = Path(skill_path).read_text(encoding="utf-8")
            if "PLUGIN_MANIFEST" in text or "plugin_manifest" in text:
                namespace: Dict[str, Any] = {}
                exec(text, namespace)
                manifest = namespace.get("PLUGIN_MANIFEST") or namespace.get("plugin_manifest") or {}
                deps = manifest.get("dependencies", [])
                for dep in deps:
                    if isinstance(dep, str):
                        results.append(self._install(dep, ""))
                    elif isinstance(dep, dict):
                        results.append(self._install(dep.get("name", ""), dep.get("version", "")))
        except Exception as exc:
            logger.debug("resolve skill deps failed: %s", exc)
        return results


dependency_resolver = DependencyResolver()
