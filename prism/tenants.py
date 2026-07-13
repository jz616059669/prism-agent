"""
PRISM Agent - 多租户隔离
同一台机器多用户/多项目独立 workspace、记忆、配置
"""

from __future__ import annotations

import json
import logging
import os
import shutil
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)

_TENANT_DIR = Path.home() / ".prism" / "tenants"
_TENANT_DIR.mkdir(parents=True, exist_ok=True)


@dataclass
class Tenant:
    id: str
    name: str = ""
    workspace: str = ""
    memory_scope: str = ""
    config_overrides: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "name": self.name,
            "workspace": self.workspace,
            "memory_scope": self.memory_scope,
            "config_overrides": self.config_overrides,
        }


class TenantStore:
    def __init__(self) -> None:
        self._tenants: Dict[str, Tenant] = {}
        self._load()

    def _load(self) -> None:
        for tenant_file in _TENANT_DIR.glob("*.json"):
            try:
                data = json.loads(tenant_file.read_text(encoding="utf-8"))
                tenant = Tenant(**data)
                self._tenants[tenant.id] = tenant
            except Exception:
                continue

    def create(self, tenant: Tenant) -> Tenant:
        self._tenants[tenant.id] = tenant
        self._save(tenant)
        return tenant

    def get(self, tenant_id: str) -> Optional[Tenant]:
        return self._tenants.get(tenant_id)

    def list_tenants(self) -> List[Dict[str, Any]]:
        return [t.to_dict() for t in self._tenants.values()]

    def remove(self, tenant_id: str) -> bool:
        if tenant_id not in self._tenants:
            return False
        del self._tenants[tenant_id]
        try:
            (_TENANT_DIR / f"{tenant_id}.json").unlink()
        except Exception:
            pass
        return True

    def _save(self, tenant: Tenant) -> None:
        try:
            (_TENANT_DIR / f"{tenant.id}.json").write_text(
                json.dumps(tenant.to_dict(), ensure_ascii=False, indent=2), encoding="utf-8"
            )
        except Exception:
            pass


tenant_store = TenantStore()
