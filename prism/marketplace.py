"""
PRISM Agent - Agent Marketplace
发布/下载预配置 Agent（角色+技能+工作流打包）
"""

from __future__ import annotations

import hashlib
import json
import logging
import zipfile
from dataclasses import dataclass, field, asdict
from pathlib import Path
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)

_MARKET_DIR = Path.home() / ".prism" / "marketplace"
_MARKET_DIR.mkdir(parents=True, exist_ok=True)


@dataclass
class AgentPackage:
    name: str
    version: str = "1.0.0"
    description: str = ""
    author: str = ""
    persona: Dict[str, Any] = field(default_factory=dict)
    skills: List[str] = field(default_factory=list)
    workflows: List[str] = field(default_factory=list)
    tags: List[str] = field(default_factory=list)
    sha256: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

    def compute_sha(self, data: bytes) -> None:
        self.sha256 = hashlib.sha256(data).hexdigest()[:16]


class Marketplace:
    def __init__(self) -> None:
        self._packages: Dict[str, AgentPackage] = {}
        self._load_local()

    def _load_local(self) -> None:
        for pkg_file in _MARKET_DIR.glob("*.json"):
            try:
                data = json.loads(pkg_file.read_text(encoding="utf-8"))
                pkg = AgentPackage(**data)
                self._packages[pkg.name] = pkg
            except Exception:
                continue

    def publish(self, pkg: AgentPackage) -> AgentPackage:
        payload = json.dumps(pkg.to_dict(), ensure_ascii=False, sort_keys=True).encode("utf-8")
        pkg.compute_sha(payload)
        (_MARKET_DIR / f"{pkg.name}.json").write_bytes(payload)
        self._packages[pkg.name] = pkg
        return pkg

    def list_packages(self) -> List[Dict[str, Any]]:
        return [p.to_dict() for p in self._packages.values()]

    def get(self, name: str) -> Optional[AgentPackage]:
        return self._packages.get(name)

    def install(self, name: str) -> Dict[str, Any]:
        pkg = self._packages.get(name)
        if not pkg:
            return {"success": False, "error": f"package not found: {name}"}
        return {"success": True, "package": pkg.to_dict()}

    def remove(self, name: str) -> bool:
        if name not in self._packages:
            return False
        del self._packages[name]
        try:
            (_MARKET_DIR / f"{name}.json").unlink()
        except Exception:
            pass
        return True


marketplace = Marketplace()
