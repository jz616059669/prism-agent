"""
PRISM Agent - 自动翻译
对话实时翻译
"""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


@dataclass
class Translation:
    source: str = ""
    target: str = ""
    text: str = ""
    translated: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return {
            "source": self.source,
            "target": self.target,
            "text": self.text,
            "translated": self.translated,
        }


class AutoTranslator:
    _RULE_MAP = {
        "zh->en": {"你好": "hello", "谢谢": "thanks", "是": "yes", "不是": "no"},
        "en->zh": {"hello": "你好", "thanks": "谢谢", "yes": "是", "no": "不是"},
    }

    def translate(self, text: str, source: str = "zh", target: str = "en") -> Translation:
        key = f"{source}->{target}"
        translated = text
        mapping = self._RULE_MAP.get(key, {})
        for k, v in mapping.items():
            if k in translated:
                translated = translated.replace(k, v)
        return Translation(source=source, target=target, text=text, translated=translated)

    def detect_language(self, text: str) -> str:
        text = text or ""
        if any("\u4e00" <= ch <= "\u9fff" for ch in text):
            return "zh"
        return "en"


auto_translator = AutoTranslator()
