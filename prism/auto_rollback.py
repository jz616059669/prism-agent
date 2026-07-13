"""
PRISM Agent - Auto Rollback 自动回滚
基于 git 快速回滚到上一个已知好状态
"""

from __future__ import annotations

import logging
import os
import subprocess
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


@dataclass
class RollbackResult:
    success: bool
    commit: str = ""
    dry_run: bool = False
    error: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return {
            "success": self.success,
            "commit": self.commit,
            "dry_run": self.dry_run,
            "error": self.error,
        }


class AutoRollback:
    def __init__(self, repo_path: Optional[str] = None) -> None:
        self.repo_path = Path(repo_path or os.getcwd())

    def last_good(self) -> Optional[str]:
        try:
            result = subprocess.run(
                ["git", "log", "--oneline", "--grep", "fix", "--grep", "good", "--all-match", "-1"],
                cwd=self.repo_path, capture_output=True, text=True, timeout=30
            )
            if result.returncode == 0 and result.stdout.strip():
                return result.stdout.strip().split(" ")[0]
            result = subprocess.run(
                ["git", "log", "--oneline", "-1"],
                cwd=self.repo_path, capture_output=True, text=True, timeout=30
            )
            if result.returncode == 0 and result.stdout.strip():
                return result.stdout.strip().split(" ")[0]
        except Exception:
            pass
        return None

    def rollback(self, target: Optional[str] = None, dry_run: bool = True) -> RollbackResult:
        target = target or self.last_good()
        if not target:
            return RollbackResult(success=False, dry_run=dry_run, error="no target commit")
        try:
            if dry_run:
                result = subprocess.run(
                    ["git", "diff", target, "--stat"],
                    cwd=self.repo_path, capture_output=True, text=True, timeout=30
                )
                if result.returncode == 0:
                    return RollbackResult(success=True, commit=target, dry_run=dry_run)
                return RollbackResult(success=False, dry_run=dry_run, error=result.stderr)
            result = subprocess.run(
                ["git", "reset", "--hard", target],
                cwd=self.repo_path, capture_output=True, text=True, timeout=30
            )
            if result.returncode == 0:
                return RollbackResult(success=True, commit=target, dry_run=dry_run)
            return RollbackResult(success=False, dry_run=dry_run, error=result.stderr)
        except Exception as exc:
            return RollbackResult(success=False, dry_run=dry_run, error=str(exc))


auto_rollback = AutoRollback()
