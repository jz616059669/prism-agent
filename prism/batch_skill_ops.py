"""
PRISM Agent - 批量技能操作
批量启用/禁用/更新
"""

from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


class BatchSkillOps:
    def batch_disable(self, skill_names: List[str]) -> Dict[str, Any]:
        results = []
        for name in skill_names:
            try:
                from prism.skills import skill_registry
                skill = skill_registry.skills.get(name)
                if skill:
                    skill.enabled = False
                    results.append({"name": name, "disabled": True})
                else:
                    results.append({"name": name, "disabled": False, "error": "not found"})
            except Exception as exc:
                results.append({"name": name, "disabled": False, "error": str(exc)})
        return {"success": True, "results": results}

    def batch_enable(self, skill_names: List[str]) -> Dict[str, Any]:
        results = []
        for name in skill_names:
            try:
                from prism.skills import skill_registry
                skill = skill_registry.skills.get(name)
                if skill:
                    skill.enabled = True
                    results.append({"name": name, "enabled": True})
                else:
                    results.append({"name": name, "enabled": False, "error": "not found"})
            except Exception as exc:
                results.append({"name": name, "enabled": False, "error": str(exc)})
        return {"success": True, "results": results}

    def list_enabled(self) -> List[str]:
        try:
            from prism.skills import skill_registry
            return [name for name, skill in skill_registry.skills.items() if getattr(skill, "enabled", True)]
        except Exception:
            return []

    def list_disabled(self) -> List[str]:
        try:
            from prism.skills import skill_registry
            return [name for name, skill in skill_registry.skills.items() if not getattr(skill, "enabled", True)]
        except Exception:
            return []


batch_skill_ops = BatchSkillOps()
