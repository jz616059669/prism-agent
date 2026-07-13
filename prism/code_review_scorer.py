"""
PRISM Agent - 代码审查评分
自动给代码打质量分
"""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


@dataclass
class ReviewScore:
    filename: str = ""
    score: float = 0.0
    issues: List[str] = field(default_factory=list)
    suggestions: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "filename": self.filename,
            "score": round(self.score, 1),
            "issues": list(self.issues),
            "suggestions": list(self.suggestions),
        }


class CodeReviewScorer:
    def score_file(self, file_path: str) -> ReviewScore:
        path = __import__("pathlib").Path(file_path)
        if not path.exists():
            return ReviewScore(filename=file_path, score=0.0, issues=["file not found"])
        try:
            text = path.read_text(encoding="utf-8", errors="ignore")
        except Exception as exc:
            return ReviewScore(filename=file_path, score=0.0, issues=[str(exc)])
        return self.score_text(file_path, text)

    def score_text(self, filename: str, text: str) -> ReviewScore:
        lines = (text or "").splitlines()
        issues: List[str] = []
        suggestions: List[str] = []
        if len(lines) > 300:
            issues.append("文件过长，建议拆分")
        if text.count("import ") > 40:
            suggestions.append("import 过多，建议分组")
        bare_except = sum(1 for line in lines if line.strip() == "except:")
        if bare_except:
            issues.append(f"bare except 出现 {bare_except} 次")
        has_type_hint = sum(1 for line in lines if "->" in line or ": " in line.split("#")[0]) / max(1, len(lines))
        if has_type_hint < 0.05:
            suggestions.append("缺少类型注解")
        score = max(0.0, 100.0 - len(issues) * 15 - len(suggestions) * 5 - (0.1 if len(lines) > 300 else 0))
        return ReviewScore(filename=filename, score=score, issues=issues, suggestions=suggestions)


code_review_scorer = CodeReviewScorer()
