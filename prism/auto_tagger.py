"""
PRISM Agent - 自动标签生成
根据内容自动打标签
"""

from __future__ import annotations

import json
import logging
import re
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)

_TAG_RULES = {
    "code": ["def ", "class ", "import ", "```"],
    "math": ["+", "-", "*", "/", "=", "\\sum", "\\int"],
    "error": ["error", "exception", "traceback", "failed"],
    "todo": ["TODO", "FIXME", "待办", "以后"],
    "idea": ["idea", "建议", "也许", "可能"],
}


class AutoTagger:
    def tag(self, text: str, max_tags: int = 3) -> List[str]:
        text = (text or "").lower()
        scores: Dict[str, int] = {}
        for tag, keywords in _TAG_RULES.items():
            score = sum(1 for kw in keywords if kw.lower() in text)
            if score:
                scores[tag] = score
        ranked = sorted(scores.items(), key=lambda x: x[1], reverse=True)
        return [tag for tag, _ in ranked[:max_tags]]


auto_tagger = AutoTagger()
