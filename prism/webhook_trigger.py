"""
PRISM Agent - Webhook 触发器
接收外部 webhook 自动触发任务
"""

from __future__ import annotations

import json
import logging
import os
import subprocess
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)

_WEBHOOK_DIR = Path.home() / ".prism" / "webhooks"
_WEBHOOK_DIR.mkdir(parents=True, exist_ok=True)


@dataclass
class Webhook:
    id: str
    path: str = ""
    secret: str = ""
    command: str = ""
    enabled: bool = True
    created_at: float = field(default_factory=lambda: __import__("time").time())

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "path": self.path,
            "secret": self.secret,
            "command": self.command,
            "enabled": self.enabled,
            "created_at": self.created_at,
        }


class WebhookTrigger:
    def __init__(self) -> None:
        self._webhooks: Dict[str, Webhook] = {}
        self._load()

    def _load(self) -> None:
        for webhook_file in _WEBHOOK_DIR.glob("*.json"):
            try:
                data = json.loads(webhook_file.read_text(encoding="utf-8"))
                webhook = Webhook(**data)
                self._webhooks[webhook.id] = webhook
            except Exception:
                continue

    def register(self, webhook: Webhook) -> Webhook:
        self._webhooks[webhook.id] = webhook
        self._save(webhook)
        return webhook

    def trigger(self, webhook_id: str, payload: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        webhook = self._webhooks.get(webhook_id)
        if not webhook or not webhook.enabled:
            return {"success": False, "error": "webhook not found or disabled"}
        try:
            env = os.environ.copy()
            env["PRISM_WEBHOOK_ID"] = webhook_id
            env["PRISM_WEBHOOK_PAYLOAD"] = json.dumps(payload or {}, ensure_ascii=False)
            proc = subprocess.run(webhook.command, shell=True, capture_output=True, text=True, timeout=60, env=env)
            return {"success": proc.returncode == 0, "stdout": proc.stdout, "stderr": proc.stderr}
        except Exception as exc:
            return {"success": False, "error": str(exc)}

    def list_webhooks(self) -> List[Dict[str, Any]]:
        return [w.to_dict() for w in self._webhooks.values()]

    def _save(self, webhook: Webhook) -> None:
        try:
            (_WEBHOOK_DIR / f"{webhook.id}.json").write_text(
                json.dumps(webhook.to_dict(), ensure_ascii=False, indent=2),
                encoding="utf-8",
            )
        except Exception:
            pass


webhook_trigger = WebhookTrigger()
