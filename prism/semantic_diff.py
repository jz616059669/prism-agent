"""
PRISM Agent - Semantic Diff 语义化 diff
基于 AST 分类 API 变更/重构/Bugfix
"""

from __future__ import annotations

import ast
import logging
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


@dataclass
class SemanticChange:
    path: str
    category: str = "other"
    name: str = ""
    before: str = ""
    after: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return {
            "path": self.path,
            "category": self.category,
            "name": self.name,
            "before": self.before,
            "after": self.after,
        }


class SemanticDiff:
    def analyze(self, base_text: str, target_text: str, path: str = "") -> List[SemanticChange]:
        changes: List[SemanticChange] = []
        try:
            base_tree = ast.parse(base_text) if base_text.strip() else ast.parse("")
        except Exception:
            base_tree = None
        try:
            target_tree = ast.parse(target_text) if target_text.strip() else ast.parse("")
        except Exception:
            target_tree = None
        if base_tree is None or target_tree is None:
            return changes
        base_funcs = {n.name: n for n in base_tree.body if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef))}
        target_funcs = {n.name: n for n in target_tree.body if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef))}
        for name in set(base_funcs) | set(target_funcs):
            if name in base_funcs and name not in target_funcs:
                changes.append(SemanticChange(path=path, category="removed", name=name, before=name, after=""))
            elif name not in base_funcs and name in target_funcs:
                changes.append(SemanticChange(path=path, category="added", name=name, before="", after=name))
            else:
                before_code = self._unparse(base_funcs[name])
                after_code = self._unparse(target_funcs[name])
                if before_code != after_code:
                    if "self" in before_code and "self" in after_code:
                        category = "refactor"
                    elif "def test_" in before_code or "def test_" in after_code:
                        category = "bugfix"
                    else:
                        category = "api_change"
                    changes.append(SemanticChange(path=path, category=category, name=name, before=before_code, after=after_code))
        return changes

    def _unparse(self, node: ast.AST) -> str:
        try:
            return ast.unparse(node)
        except Exception:
            return ""

    def diff_files(self, base_path: str, target_path: str) -> List[SemanticChange]:
        base_text = Path(base_path).read_text(encoding="utf-8", errors="ignore") if Path(base_path).exists() else ""
        target_text = Path(target_path).read_text(encoding="utf-8", errors="ignore") if Path(target_path).exists() else ""
        return self.analyze(base_text, target_text, path=target_path)


semantic_diff = SemanticDiff()
