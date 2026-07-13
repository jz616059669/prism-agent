"""
PRISM Agent - 数据脱敏
自动识别 PII 并脱敏，本地合规
"""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)

_PHONE_RE = re.compile(r"\b1[3-9]\d{9}\b")
_EMAIL_RE = re.compile(r"[A-Za-z0-9._%+\-]+@[A-Za-z0-9.\-]+\.[A-Za-z]{2,}")
_ID_CARD_RE = re.compile(r"\b\d{17}[\dXx]\b")
_BANK_CARD_RE = re.compile(r"\b\d{16,19}\b")


@dataclass
class DesensitizeResult:
    original: str = ""
    desensitized: str = ""
    replaced_count: int = 0
    categories: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "original": self.original,
            "desensitized": self.desensitized,
            "replaced_count": self.replaced_count,
            "categories": list(self.categories),
        }


class DataDesensitizer:
    def redact(self, text: str) -> DesensitizeResult:
        result = DesensitizeResult(original=text)
        output = text
        mappings = [
            (_PHONE_RE, "phone", "[手机号脱敏]"),
            (_EMAIL_RE, "email", "[邮箱脱敏]"),
            (_ID_CARD_RE, "id_card", "[身份证脱敏]"),
            (_BANK_CARD_RE, "bank_card", "[银行卡脱敏]"),
        ]
        for pattern, category, placeholder in mappings:
            matches = pattern.findall(output)
            if matches:
                result.replaced_count += len(matches)
                result.categories.append(category)
                output = pattern.sub(placeholder, output)
        result.desensitized = output
        return result


data_desensitizer = DataDesensitizer()
