"""
PRISM Agent - 技能冲突检测
安装 skill 时检测冲突
"""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


@dataclass
class ConflictIssue:
    source: str
    target: str
    reason: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return {
            "source": self.source,
            "target": self.target,
            "reason": self.reason,
        }


class SkillConflictDetector:
    def check(self, new_skill: str, installed_skills: List[str]) -> List[ConflictIssue]:
        issues: List[ConflictIssue] = []
        for skill in installed_skills:
            if new_skill == skill:
                issues.append(ConflictIssue(source=new_skill, target=skill, reason="同名 skill 已安装"))
                continue
            base_new = new_skill.split(".")[-1].lower()
            base_installed = skill.split(".")[-1].lower()
            if base_new and base_new == base_installed and base_new not in ("prism", "agent"):
                issues.append(ConflictIssue(source=new_skill, target=skill, reason="模块名冲突"))
        return issues

    def has_conflict(self, new_skill: str, installed_skills: List[str]) -> bool:
        return len(self.check(new_skill, installed_skills)) > 0


skill_conflict_detector = SkillConflictDetector()
