"""
PRISM Agent - GraphQL API
提供 GraphQL 接口替代 REST
"""

from __future__ import annotations

import json
import logging
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


class GraphQLEndpoint:
    def __init__(self) -> None:
        self._schema: Dict[str, Any] = {
            "query": {
                "hello": "String!",
                "skills": "[Skill!]!",
                "health": "Health!",
            },
            "type": {
                "Skill": {"name": "String!", "enabled": "Boolean!"},
                "Health": {"status": "String!", "uptime": "Float!"},
            },
        }

    def schema(self) -> Dict[str, Any]:
        return self._schema

    def execute(self, query: str, variables: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        variables = variables or {}
        query = (query or "").strip()
        if not query:
            return {"errors": [{"message": "empty query"}]}
        if query == "{ hello }":
            return {"data": {"hello": "PRISM GraphQL"}}
        if query == "{ skills { name enabled } }":
            try:
                from prism.skills import skill_registry
                skills = [{"name": name, "enabled": getattr(skill, "enabled", True)} for name, skill in skill_registry.skills.items()]
                return {"data": {"skills": skills}}
            except Exception as exc:
                return {"data": {"skills": []}, "errors": [{"message": str(exc)}]}
        if query == "{ health { status uptime } }":
            try:
                from prism.health_monitor import health_monitor
                checks = health_monitor.list_checks()
                status = "ok" if any(c.get("status") == "running" for c in checks) else "unknown"
                uptime = max([c.get("last_check", 0) for c in checks]) if checks else 0
                return {"data": {"health": {"status": status, "uptime": uptime}}}
            except Exception as exc:
                return {"data": {"health": {"status": "error", "uptime": 0}}, "errors": [{"message": str(exc)}]}
        return {"errors": [{"message": "unknown query"}]}


graphql_endpoint = GraphQLEndpoint()
