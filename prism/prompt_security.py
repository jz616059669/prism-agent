"""
PRISM Agent - Prompt 安全扫描
检测 prompt 注入/jailbreak，防止攻击
"""

from __future__ import annotations

import json
import logging
import re
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


@dataclass
class SecurityIssue:
    category: str = ""
    severity: str = "low"
    detail: str = ""
    evidence: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return {
            "category": self.category,
            "severity": self.severity,
            "detail": self.detail,
            "evidence": self.evidence,
        }


class PromptSecurityScanner:
    def __init__(self) -> None:
        self._patterns = [
            ("jailbreak", re.compile(r"忽略.*指令|忘记.*设定|你现在是|请扮演|DAN|越狱", re.IGNORECASE)),
            ("injection", re.compile(r"system\s*:| assistant\s*:| user\s*:|\\n\\n.*(system|assistant|user)", re.IGNORECASE)),
            ("exfil", re.compile(r"打印.*config|输出.*api_key|发送.*http|上传.*文件", re.IGNORECASE)),
            ("obfuscate", re.compile(r"base64|decode|exec\s*\(|eval\s*\(", re.IGNORECASE)),
        ]

    def scan(self, text: str) -> List[SecurityIssue]:
        issues: List[SecurityIssue] = []
        for category, pattern in self._patterns:
            matches = pattern.findall(text or "")
            if matches:
                issues.append(SecurityIssue(category=category, severity="high" if category in ("jailbreak", "injection") else "medium", detail=f"检测到 {category} 风险", evidence=matches[0]))
        return issues

    def is_safe(self, text: str) -> bool:
        return len(self.scan(text)) == 0


prompt_security_scanner = PromptSecurityScanner()
