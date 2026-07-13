"""
PRISM Agent - 自动摘要邮件
每日/每周 digest，自动推送
"""

from __future__ import annotations

import json
import logging
import smtplib
from dataclasses import dataclass, field
from email.mime.text import MIMEText
from pathlib import Path
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)

_DIGEST_DIR = Path.home() / ".prism" / "digests"
_DIGEST_DIR.mkdir(parents=True, exist_ok=True)


@dataclass
class DigestItem:
    title: str = ""
    summary: str = ""
    url: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return {
            "title": self.title,
            "summary": self.summary,
            "url": self.url,
        }


@dataclass
class Digest:
    id: str
    items: List[DigestItem] = field(default_factory=list)
    created_at: float = field(default_factory=lambda: __import__("time").time())

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "items": [i.to_dict() for i in self.items],
            "created_at": self.created_at,
        }


class DigestMailer:
    def build_daily(self, session_id: str, messages: List[Dict[str, Any]]) -> Digest:
        items = []
        for msg in messages[-10:]:
            role = msg.get("role", "")
            content = str(msg.get("content", "") or "")
            items.append(DigestItem(title=f"{role} 消息", summary=content[:120], url=""))
        return Digest(id=f"daily_{session_id}", items=items)

    def build_weekly(self, session_id: str, messages: List[Dict[str, Any]]) -> Digest:
        items = []
        for msg in messages[-30:]:
            role = msg.get("role", "")
            content = str(msg.get("content", "") or "")
            items.append(DigestItem(title=f"{role} 消息", summary=content[:120], url=""))
        return Digest(id=f"weekly_{session_id}", items=items)

    def to_markdown(self, digest: Digest) -> str:
        lines = [f"# Digest {digest.id}\n"]
        for item in digest.items:
            lines.append(f"- **{item.title}**: {item.summary}")
        return "\n".join(lines)

    def send_email(self, to_email: str, subject: str, body: str, smtp_host: str = "smtp.qq.com", smtp_port: int = 587, username: str = "", password: str = "") -> Dict[str, Any]:
        msg = MIMEText(body, "plain", "utf-8")
        msg["Subject"] = subject
        msg["From"] = username
        msg["To"] = to_email
        try:
            with smtplib.SMTP(smtp_host, smtp_port) as server:
                server.starttls()
                server.login(username, password)
                server.sendmail(username, [to_email], msg.as_string())
            return {"success": True}
        except Exception as exc:
            return {"success": False, "error": str(exc)}


digest_mailer = DigestMailer()
