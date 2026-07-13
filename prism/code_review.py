"""
PRISM Agent - 自动化代码审查 Bot
监听 git diff，自动 review + 生成 PR comment
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
class ReviewComment:
    path: str
    line: int
    severity: str = "info"
    message: str = ""
    suggestion: str = ""


class CodeReviewBot:
    def __init__(self, repo_path: Optional[str] = None) -> None:
        self.repo_path = Path(repo_path or os.getcwd())

    def get_diff(self, base: str = "HEAD", target: str = "") -> str:
        try:
            cmd = ["git", "diff", base, target, "--no-color"]
            result = subprocess.run(cmd, cwd=self.repo_path, capture_output=True, text=True, timeout=30)
            return result.stdout
        except Exception as exc:
            logger.debug("git diff failed: %s", exc)
            return ""

    def review_diff(self, diff_text: str) -> List[ReviewComment]:
        comments: List[ReviewComment] = []
        current_path = ""
        for line in diff_text.splitlines():
            if line.startswith("diff --git"):
                parts = line.split(" ")
                if len(parts) >= 4:
                    current_path = parts[2][2:] if parts[2].startswith("b/") else parts[2]
            elif line.startswith("@@"):
                try:
                    line_no = int(line.split("+")[1].split(",")[0])
                except Exception:
                    line_no = 0
            elif line.startswith("+") and not line.startswith("+++"):
                content = line[1:]
                if "import os" in content or "import sys" in content:
                    comments.append(ReviewComment(path=current_path, line=line_no, severity="warning", message="检测到 os/sys 调用，注意安全", suggestion="确认是否经过参数校验"))
                if "eval(" in content or "exec(" in content:
                    comments.append(ReviewComment(path=current_path, line=line_no, severity="error", message="检测到 eval/exec，高风险", suggestion="改用 AST 解析或白名单"))
                if "password" in content.lower() or "secret" in content.lower():
                    comments.append(ReviewComment(path=current_path, line=line_no, severity="error", message="疑似硬编码敏感信息", suggestion="改用环境变量或密钥管理"))
        return comments

    def review_commit(self, base: str = "HEAD~1", target: str = "HEAD") -> Dict[str, Any]:
        diff = self.get_diff(base, target)
        if not diff:
            return {"success": True, "comments": []}
        comments = self.review_diff(diff)
        return {
            "success": True,
            "base": base,
            "target": target,
            "comments": [c.__dict__ for c in comments],
            "summary": {
                "total": len(comments),
                "errors": sum(1 for c in comments if c.severity == "error"),
                "warnings": sum(1 for c in comments if c.severity == "warning"),
            },
        }


code_review_bot = CodeReviewBot()
