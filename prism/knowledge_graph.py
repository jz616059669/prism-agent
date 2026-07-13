"""
PRISM Agent - 知识图谱记忆
实体关系图谱：人物/事件/设定关联
"""

from __future__ import annotations

import json
import logging
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)

_GRAPH_DIR = Path.home() / ".prism" / "graph"
_GRAPH_DIR.mkdir(parents=True, exist_ok=True)


@dataclass
class Entity:
    id: str
    name: str
    type: str = "entity"
    properties: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "name": self.name,
            "type": self.type,
            "properties": self.properties,
        }


@dataclass
class Relation:
    source: str
    target: str
    relation: str
    properties: Dict[str, Any] = field(default_factory=dict)
    ts: float = field(default_factory=time.time)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "source": self.source,
            "target": self.target,
            "relation": self.relation,
            "properties": self.properties,
            "ts": self.ts,
        }


class KnowledgeGraph:
    def __init__(self) -> None:
        self._entities: Dict[str, Entity] = {}
        self._relations: List[Relation] = []
        self._load()

    def _load(self) -> None:
        ent_file = _GRAPH_DIR / "entities.json"
        rel_file = _GRAPH_DIR / "relations.json"
        if ent_file.exists():
            try:
                for item in json.loads(ent_file.read_text(encoding="utf-8")):
                    e = Entity(**item)
                    self._entities[e.id] = e
            except Exception:
                pass
        if rel_file.exists():
            try:
                self._relations = [Relation(**r) for r in json.loads(rel_file.read_text(encoding="utf-8"))]
            except Exception:
                pass

    def _save(self) -> None:
        try:
            (_GRAPH_DIR / "entities.json").write_text(
                json.dumps([e.to_dict() for e in self._entities.values()], ensure_ascii=False, indent=2),
                encoding="utf-8",
            )
            (_GRAPH_DIR / "relations.json").write_text(
                json.dumps([r.to_dict() for r in self._relations], ensure_ascii=False, indent=2),
                encoding="utf-8",
            )
        except Exception:
            pass

    def add_entity(self, entity: Entity) -> Entity:
        self._entities[entity.id] = entity
        self._save()
        return entity

    def add_relation(self, source: str, target: str, relation: str, properties: Optional[Dict[str, Any]] = None) -> Relation:
        rel = Relation(source=source, target=target, relation=relation, properties=properties or {})
        self._relations.append(rel)
        self._save()
        return rel

    def query_related(self, entity_id: str, relation: Optional[str] = None, max_depth: int = 2) -> List[Dict[str, Any]]:
        results: List[Dict[str, Any]] = []
        visited = set()
        queue = [(entity_id, 0)]
        while queue:
            current, depth = queue.pop(0)
            if current in visited or depth > max_depth:
                continue
            visited.add(current)
            for rel in self._relations:
                if rel.source == current and relation in (None, rel.relation):
                    results.append({"from": rel.source, "to": rel.target, "relation": rel.relation, "depth": depth + 1})
                    if depth + 1 <= max_depth:
                        queue.append((rel.target, depth + 1))
                elif rel.target == current and relation in (None, rel.relation):
                    results.append({"from": rel.source, "to": rel.target, "relation": rel.relation, "depth": depth + 1})
                    if depth + 1 <= max_depth:
                        queue.append((rel.source, depth + 1))
        return results

    def list_entities(self) -> List[Dict[str, Any]]:
        return [e.to_dict() for e in self._entities.values()]

    def list_relations(self) -> List[Dict[str, Any]]:
        return [r.to_dict() for r in self._relations]

    def shortest_path(self, source: str, target: str, max_depth: int = 4) -> List[Dict[str, Any]]:
        if source == target:
            return [{"source": source, "target": target, "relation": "self", "depth": 0}]
        queue: List[tuple[str, List[Dict[str, Any]]]] = [(source, [])]
        visited = {source}
        while queue:
            current, path = queue.pop(0)
            if len(path) >= max_depth:
                continue
            for rel in self._relations:
                next_node = None
                if rel.source == current:
                    next_node = rel.target
                elif rel.target == current:
                    next_node = rel.source
                else:
                    continue
                edge = {"from": rel.source, "to": rel.target, "relation": rel.relation}
                new_path = path + [edge]
                if next_node == target:
                    return new_path
                if next_node not in visited:
                    visited.add(next_node)
                    queue.append((next_node, new_path))
        return []


knowledge_graph = KnowledgeGraph()
