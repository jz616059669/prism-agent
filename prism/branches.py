"""
PRISM Agent - 对话分支 / 时间旅行
支持回滚到任意历史消息重新生成，不丢失上下文
"""

from __future__ import annotations

import json
import logging
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)

_BRANCH_DIR = Path.home() / ".prism" / "branches"
_BRANCH_DIR.mkdir(parents=True, exist_ok=True)


@dataclass
class MessageBranch:
    id: str
    session_id: str
    messages: List[Dict[str, Any]] = field(default_factory=list)
    parent_branch_id: str = ""
    branch_point_index: int = 0
    created_at: float = field(default_factory=time.time)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "session_id": self.session_id,
            "messages": self.messages,
            "parent_branch_id": self.parent_branch_id,
            "branch_point_index": self.branch_point_index,
            "created_at": self.created_at,
        }


class BranchStore:
    def __init__(self) -> None:
        self._branches: Dict[str, MessageBranch] = {}
        self._load()

    def _load(self) -> None:
        for branch_file in _BRANCH_DIR.glob("*.json"):
            try:
                data = json.loads(branch_file.read_text(encoding="utf-8"))
                branch = MessageBranch(**data)
                self._branches[branch.id] = branch
            except Exception:
                continue

    def create_branch(self, session_id: str, messages: List[Dict[str, Any]], branch_point_index: int, parent_branch_id: str = "") -> MessageBranch:
        branch = MessageBranch(
            id=f"branch_{int(time.time())}_{len(messages)}",
            session_id=session_id,
            messages=list(messages),
            parent_branch_id=parent_branch_id,
            branch_point_index=branch_point_index,
        )
        self._branches[branch.id] = branch
        self._save(branch)
        return branch

    def get_branch(self, branch_id: str) -> Optional[MessageBranch]:
        return self._branches.get(branch_id)

    def list_branches(self, session_id: str) -> List[Dict[str, Any]]:
        return [b.to_dict() for b in self._branches.values() if b.session_id == session_id]

    def _save(self, branch: MessageBranch) -> None:
        try:
            (_BRANCH_DIR / f"{branch.id}.json").write_text(
                json.dumps(branch.to_dict(), ensure_ascii=False, indent=2),
                encoding="utf-8",
            )
        except Exception:
            pass


branch_store = BranchStore()
