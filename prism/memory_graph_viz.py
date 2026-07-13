"""
PRISM Agent - 记忆图谱可视化
知识图谱 + 关系图，支持 JSON / Mermaid 导出
"""

from __future__ import annotations

import json
import logging
from typing import Any, Dict, List, Optional

from prism.knowledge_graph import knowledge_graph

logger = logging.getLogger(__name__)


class MemoryGraphVisualizer:
    def to_json(self, entity_id: str, max_depth: int = 2) -> Dict[str, Any]:
        nodes: List[Dict[str, Any]] = []
        links: List[Dict[str, Any]] = []
        visited = set()
        queue = [(entity_id, 0)]
        while queue:
            current, depth = queue.pop(0)
            if current in visited or depth > max_depth:
                continue
            visited.add(current)
            entity = knowledge_graph._entities.get(current)
            if entity:
                nodes.append({"id": entity.id, "name": entity.name, "type": entity.type})
            for rel in knowledge_graph._relations:
                if rel.source == current:
                    links.append({"source": rel.source, "target": rel.target, "relation": rel.relation})
                    if depth + 1 <= max_depth:
                        queue.append((rel.target, depth + 1))
                elif rel.target == current:
                    links.append({"source": rel.source, "target": rel.target, "relation": rel.relation})
                    if depth + 1 <= max_depth:
                        queue.append((rel.source, depth + 1))
        return {"nodes": nodes, "links": links}

    def to_mermaid(self, entity_id: str, max_depth: int = 2) -> str:
        data = self.to_json(entity_id, max_depth=max_depth)
        lines = ["graph LR"]
        for node in data.get("nodes", []):
            lines.append(f'    {node["id"]}["{node["name"]}"]')
        for link in data.get("links", []):
            lines.append(f'    {link["source"]} -->|{link["relation"]}| {link["target"]}')
        return "\n".join(lines)


memory_graph_visualizer = MemoryGraphVisualizer()
