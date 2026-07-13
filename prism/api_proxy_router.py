"""
PRISM Agent - API 代理/路由
统一 API 入口，负载均衡
"""

from __future__ import annotations

import json
import logging
import random
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)

_PROXY_DIR = Path.home() / ".prism" / "proxy"
_PROXY_DIR.mkdir(parents=True, exist_ok=True)


@dataclass
class ProxyEndpoint:
    name: str
    base_url: str = ""
    provider: str = ""
    api_key: str = ""
    priority: int = 0
    weight: int = 1
    healthy: bool = True

    def to_dict(self) -> Dict[str, Any]:
        return {
            "name": self.name,
            "base_url": self.base_url,
            "provider": self.provider,
            "priority": self.priority,
            "weight": self.weight,
            "healthy": self.healthy,
        }


class ApiProxyRouter:
    def __init__(self) -> None:
        self._endpoints: Dict[str, ProxyEndpoint] = {}
        self._load()

    def _load(self) -> None:
        for ep_file in _PROXY_DIR.glob("*.json"):
            try:
                data = json.loads(ep_file.read_text(encoding="utf-8"))
                ep = ProxyEndpoint(**data)
                self._endpoints[ep.name] = ep
            except Exception:
                continue

    def register(self, endpoint: ProxyEndpoint) -> ProxyEndpoint:
        self._endpoints[endpoint.name] = endpoint
        self._save(endpoint)
        return endpoint

    def route(self, provider: str = "") -> Optional[ProxyEndpoint]:
        candidates = [ep for ep in self._endpoints.values() if ep.healthy and (not provider or ep.provider == provider)]
        if not candidates:
            return None
        candidates.sort(key=lambda ep: (ep.priority, random.random()), reverse=True)
        return candidates[0]

    def mark_down(self, name: str) -> Optional[ProxyEndpoint]:
        ep = self._endpoints.get(name)
        if not ep:
            return None
        ep.healthy = False
        self._save(ep)
        return ep

    def list_endpoints(self) -> List[Dict[str, Any]]:
        return [ep.to_dict() for ep in self._endpoints.values()]

    def _save(self, endpoint: ProxyEndpoint) -> None:
        try:
            (_PROXY_DIR / f"{endpoint.name}.json").write_text(
                json.dumps(endpoint.to_dict(), ensure_ascii=False, indent=2),
                encoding="utf-8",
            )
        except Exception:
            pass


api_proxy_router = ApiProxyRouter()
