"""
PRISM Agent - Plugin API 插件协议
第三方 skill 标准入口/清单/钩子
"""

from __future__ import annotations

import ast
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional

from prism.logging import logger
from prism.dependency_resolver import DependencyResolver


@dataclass
class PluginManifest:
    name: str
    version: str = "1.0.0"
    entry: str = "main"
    description: str = ""
    author: str = ""
    dependencies: List[str] = field(default_factory=list)
    hooks: List[str] = field(default_factory=list)
    permissions: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "name": self.name,
            "version": self.version,
            "entry": self.entry,
            "description": self.description,
            "author": self.author,
            "dependencies": self.dependencies,
            "hooks": self.hooks,
            "permissions": self.permissions,
        }


class PluginLoader:
    def __init__(self, skills_dir: Optional[str] = None) -> None:
        self.skills_dir = Path(skills_dir or Path.home() / ".prism" / "skills")

    def load_manifest(self, skill_name: str) -> Optional[PluginManifest]:
        skill_file = self.skills_dir / f"{skill_name}.py"
        if not skill_file.exists():
            return None
        try:
            text = skill_file.read_text(encoding="utf-8")
            return PluginLoader._parse_manifest(text, skill_name)
        except Exception:
            return None

    def list_manifests(self) -> List[Dict[str, Any]]:
        manifests: List[Dict[str, Any]] = []
        if not self.skills_dir.exists():
            return manifests
        for skill_file in self.skills_dir.glob("*.py"):
            if skill_file.name.startswith("test_") or skill_file.name == "__init__.py":
                continue
            manifest = self.load_manifest(skill_file.stem)
            if manifest:
                manifests.append(manifest.to_dict())
        return manifests

    @staticmethod
    def _parse_manifest(text: str, skill_name: str) -> Optional[PluginManifest]:
        try:
            manifest = DependencyResolver._extract_manifest(text)
            if isinstance(manifest, dict):
                return PluginManifest(
                    name=manifest.get("name", skill_name),
                    version=manifest.get("version", "1.0.0"),
                    entry=manifest.get("entry", "main"),
                    description=manifest.get("description", ""),
                    author=manifest.get("author", ""),
                    dependencies=manifest.get("dependencies", []),
                    hooks=manifest.get("hooks", []),
                    permissions=manifest.get("permissions", []),
                )
        except Exception:
            pass
        return None


plugin_loader = PluginLoader()
