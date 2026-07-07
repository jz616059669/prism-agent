"""
PRISM memory graph — lightweight learning graph for desktop.
Nodes: memory entries + skills
Edges: lexical overlap (shared tokens)
Output: JSON payload consumable by desktop/CLI renderers.
"""

from __future__ import annotations

import json
import re
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from prism.memory import persistent_memory
from prism.skills import skills as skill_registry


@dataclass
class GraphNode:
    id: str
    label: str
    kind: str  # memory | skill
    category: str = ""
    timestamp: Optional[int] = None
    use_count: int = 0
    related: List[str] = field(default_factory=list)


def _tokenize(text: str) -> set[str]:
    text = re.sub(r"[^a-zA-Z0-9\u4e00-\u9fff]", " ", text.lower())
    tokens = {t for t in text.split() if len(t) > 1}
    return tokens


def _overlap(a: set[str], b: set[str]) -> int:
    if not a or not b:
        return 0
    return len(a & b)


def build_memory_graph(max_memories: int = 200, min_overlap: int = 2) -> Dict[str, Any]:
    """Build a lightweight memory/skill graph from prism's own memory + skills."""
    try:
        nodes: List[Dict[str, Any]] = []
        edges: List[Dict[str, Any]] = []
        token_map: Dict[str, set[str]] = defaultdict(set)
        id_map: Dict[str, GraphNode] = {}

        # 1. memory nodes
        mem_items = []
        try:
            for key, entry in list(persistent_memory._index.items())[:max_memories]:
                mem_items.append((key, entry))
        except Exception:
            mem_items = []

        for key, entry in mem_items:
            value = getattr(entry, "value", "") or ""
            tokens = _tokenize(value)
            node_id = f"mem:{key}"
            node = GraphNode(
                id=node_id,
                label=value[:60] + ("…" if len(value) > 60 else ""),
                kind="memory",
                category=getattr(entry, "category", "") or "",
                timestamp=int(getattr(entry, "updated_at", datetime.now()).timestamp()) if hasattr(getattr(entry, "updated_at", None), "timestamp") else None,
                use_count=getattr(entry, "access_count", 0) or 0,
            )
            nodes.append({
                "id": node.id,
                "label": node.label,
                "kind": node.kind,
                "category": node.category,
                "timestamp": node.timestamp,
                "use_count": node.use_count,
            })
            id_map[node_id] = node
            for t in tokens:
                token_map[t].add(node_id)

        # 2. skill nodes
        try:
            for s in skill_registry.list_skills():
                node_id = f"skill:{s['name']}"
                desc = s.get("description") or ""
                tokens = _tokenize(desc)
                node = GraphNode(
                    id=node_id,
                    label=s.get("name", node_id),
                    kind="skill",
                    category="skill",
                    use_count=1 if s.get("enabled") else 0,
                    related=s.get("related", []),
                )
                nodes.append({
                    "id": node.id,
                    "label": node.label,
                    "kind": node.kind,
                    "category": node.category,
                    "timestamp": None,
                    "use_count": node.use_count,
                })
                id_map[node_id] = node
                for t in tokens:
                    token_map[t].add(node_id)
        except Exception:
            pass

        # 3. edges from shared tokens
        seen_edges = set()
        for token, ids in token_map.items():
            ids = list(ids)
            if len(ids) < 2:
                continue
            for i in range(len(ids)):
                for j in range(i + 1, len(ids)):
                    a, b = ids[i], ids[j]
                    if a == b:
                        continue
                    na, nb = id_map.get(a), id_map.get(b)
                    if not na or not nb:
                        continue
                    if _overlap(_tokenize(na.label), _tokenize(nb.label)) < min_overlap:
                        continue
                    key = (a, b) if a < b else (b, a)
                    if key in seen_edges:
                        continue
                    seen_edges.add(key)
                    edges.append({
                        "source": key[0],
                        "target": key[1],
                        "weight": 1,
                        "label": token,
                    })

        return {
            "success": True,
            "graph": {
                "nodes": nodes,
                "edges": edges,
            },
            "stats": {
                "nodes": len(nodes),
                "edges": len(edges),
            },
        }
    except Exception as exc:
        return {"success": False, "error": str(exc)}


def render_graph_mermaid(payload: Dict[str, Any]) -> str:
    """Render graph as a compact Mermaid snippet for desktop preview."""
    try:
        graph = payload.get("graph", {})
        lines = ["graph LR"]
        for node in graph.get("nodes", []):
            shape = "[(%s)]" if node.get("kind") == "memory" else "(%s)"
            label = (node.get("label") or node.get("id", "")).replace('"', "'")
            lines.append(f'  {node["id"]} {shape % label}')
        for edge in graph.get("edges", [])[:200]:
            lines.append(f'  {edge["source"]} -- {edge.get("label", "")} --> {edge["target"]}')
        return "\n".join(lines)
    except Exception as exc:
        return f"graph TD\n  error[\"render failed: {exc}\"]"
