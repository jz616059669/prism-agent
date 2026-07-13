"""
PRISM Agent - 插件依赖图
可视化技能依赖关系
"""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)

_DEP_DIR = Path.home() / ".prism" / "dep_graph"
_DEP_DIR.mkdir(parents=True, exist_ok=True)


@dataclass
class PluginNode:
    name: str
    version: str = ""
    dependencies: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "name": self.name,
            "version": self.version,
            "dependencies": list(self.dependencies),
        }


class PluginDependencyGraph:
    def __init__(self) -> None:
        self._nodes: Dict[str, PluginNode] = {}
        self._load()

    def _load(self) -> None:
        for node_file in _DEP_DIR.glob("*.json"):
            try:
                data = json.loads(node_file.read_text(encoding="utf-8"))
                node = PluginNode(**data)
                self._nodes[node.name] = node
            except Exception:
                continue

    def register(self, node: PluginNode) -> PluginNode:
        self._nodes[node.name] = node
        self._save(node)
        return node

    def get(self, name: str) -> Optional[PluginNode]:
        return self._nodes.get(name)

    def dependents(self, name: str) -> List[PluginNode]:
        return [node for node in self._nodes.values() if name in node.dependencies]

    def to_mermaid(self) -> str:
        lines = ["graph LR"]
        for node in self._nodes.values():
            for dep in node.dependencies:
                lines.append(f"  {dep} --> {node.name}")
        return "\n".join(lines)

    def list_nodes(self) -> List[Dict[str, Any]]:
        return [n.to_dict() for n in self._nodes.values()]

    def _save(self, node: PluginNode) -> None:
        try:
            (_DEP_DIR / f"{node.name}.json").write_text(
                json.dumps(node.to_dict(), ensure_ascii=False, indent=2),
                encoding="utf-8",
            )
        except Exception:
            pass


plugin_dependency_graph = PluginDependencyGraph()
