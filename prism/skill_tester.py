"""
PRISM Agent - Skill 自动测试框架
安装/更新 skill 时自动跑测试用例，失败则回滚
"""

from __future__ import annotations

import importlib.util
import logging
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


@dataclass
class SkillTestResult:
    name: str
    passed: int = 0
    failed: int = 0
    error: str = ""
    traceback: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return {
            "name": self.name,
            "passed": self.passed,
            "failed": self.failed,
            "error": self.error,
            "traceback": self.traceback,
        }


class SkillTester:
    def __init__(self, skills_dir: Optional[str] = None) -> None:
        self.skills_dir = Path(skills_dir or Path.home() / ".prism" / "skills")

    def test_skill(self, skill_name: str) -> SkillTestResult:
        result = SkillTestResult(name=skill_name)
        skill_file = self.skills_dir / f"{skill_name}.py"
        if not skill_file.exists():
            result.error = f"skill file not found: {skill_file}"
            return result
        # 尝试查找同名测试文件
        test_file = self.skills_dir / f"test_{skill_name}.py"
        if not test_file.exists():
            result.passed = 0
            result.failed = 0
            result.error = "no test file"
            return result
        try:
            spec = importlib.util.spec_from_file_location(f"test_{skill_name}", test_file)
            module = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(module)
            if hasattr(module, "test_skill"):
                test_fn = getattr(module, "test_skill")
                test_fn(skill_name)
                result.passed = 1
                return result
        except Exception as exc:
            result.failed = 1
            result.error = str(exc)
            result.traceback = logging.Formatter().formatException(logging.LogRecord(
                name="skill_test", level=logging.ERROR, pathname="", lineno=0, msg=str(exc),
                args=(), exc_info=sys.exc_info()
            ))
        return result

    def test_all(self) -> List[SkillTestResult]:
        results: List[SkillTestResult] = []
        if not self.skills_dir.exists():
            return results
        for skill_file in self.skills_dir.glob("*.py"):
            if skill_file.name.startswith("test_") or skill_file.name == "__init__.py":
                continue
            results.append(self.test_skill(skill_file.stem))
        return results


skill_tester = SkillTester()
