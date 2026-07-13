"""
PRISM Agent - Agent 自我反思
自动 review 自己的输出，发现错误自我修正
"""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


@dataclass
class Reflection:
    original: str = ""
    issues: List[str] = field(default_factory=list)
    improved: str = ""
    score: float = 0.0

    def to_dict(self) -> Dict[str, Any]:
        return {
            "original": self.original,
            "issues": list(self.issues),
            "improved": self.improved,
            "score": self.score,
        }


class SelfReflection:
    def review(self, text: str) -> Reflection:
        issues: List[str] = []
        lower = (text or "").lower()
        if not lower:
            issues.append("内容为空")
        if lower.count("错误") + lower.count("抱歉") + lower.count("不对") > 2:
            issues.append("自我否定过多")
        if len(lower) < 20:
            issues.append("过短")
        if "http" in lower and "://" in lower and len(lower) < 80:
            issues.append("可能包含可疑链接")
        improved = text
        if issues:
            improved = "[已审查]\n" + text + "\n[注意事项] " + "; ".join(issues)
        score = max(0.0, 1.0 - 0.2 * len(issues))
        reflection = Reflection(original=text, issues=issues, improved=improved, score=score)
        try:
            reflection = self._llm_review(text, reflection)
        except Exception:
            pass
        return reflection

    def _llm_review(self, text: str, fallback: Reflection) -> Reflection:
        try:
            from prism.agent import create_agent
            reviewer = create_agent(enable_auto_memory=False)
            prompt = (
                "请审查以下文本，只输出 JSON：{\"issues\":[\"问题1\"], \"score\":0.9}\n"
                f"文本：\n{text[:1000]}\n"
            )
            out = reviewer.chat(user_message=prompt)
            try:
                reviewer.close()
            except Exception:
                pass
            data = json.loads(out or "{}")
            issues = data.get("issues") or fallback.issues
            score = float(data.get("score") or fallback.score)
            improved = fallback.original
            if issues:
                improved = "[已审查]\n" + improved + "\n[注意事项] " + "; ".join(issues)
            return Reflection(original=fallback.original, issues=issues, improved=improved, score=score)
        except Exception:
            return fallback

    def should_retry(self, reflection: Reflection) -> bool:
        return reflection.score < 0.6 and len(reflection.issues) >= 2


self_reflection = SelfReflection()
