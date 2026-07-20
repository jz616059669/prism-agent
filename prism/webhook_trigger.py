"""
PRISM Agent - Webhook 触发器 + HTTP Server
接收外部 webhook 自动触发任务
"""

from __future__ import annotations

import hashlib
import hmac
import json
import logging
import os
import shlex
import subprocess
import threading
import time
from dataclasses import dataclass, field
from http.server import HTTPServer, BaseHTTPRequestHandler
from pathlib import Path
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)

_WEBHOOK_DIR = Path.home() / ".prism" / "webhooks"
_WEBHOOK_DIR.mkdir(parents=True, exist_ok=True)


def _verify_signature(secret: str, timestamp: str, signature: str, body: bytes) -> bool:
    try:
        ts = int(timestamp)
    except ValueError:
        return False
    if abs(time.time() - ts) > 300:
        return False
    message = timestamp.encode("utf-8") + b"\n" + body
    expected = hmac.new(secret.encode("utf-8"), message, hashlib.sha256).hexdigest()
    return hmac.compare_digest(expected, signature)


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
            if os.name == "nt":
                proc = subprocess.run(
                    ["cmd", "/c", webhook.command],
                    capture_output=True,
                    text=True,
                    timeout=60,
                    env=env,
                )
            else:
                proc = subprocess.run(
                    shlex.split(webhook.command),
                    capture_output=True,
                    text=True,
                    timeout=60,
                    env=env,
                )
            return {"success": proc.returncode == 0, "stdout": proc.stdout, "stderr": proc.stderr}
        except Exception as exc:
            return {"success": False, "error": str(exc)}

    def list_webhooks(self) -> List[Dict[str, Any]]:
        return [w.to_dict() for w in self._webhooks.values()]

    def start_server(self, host: str = "127.0.0.1", port: int = 9900) -> Optional[threading.Thread]:
        trigger = self

        class Handler(BaseHTTPRequestHandler):
            _allowed_secret = ""

            @classmethod
            def set_allowed_secret(cls, secret: str) -> None:
                cls._allowed_secret = secret

            def log_message(self, format, *args):
                logger.debug(format, *args)

            def _send_json(self, status, data):
                body = json.dumps(data, ensure_ascii=False).encode("utf-8")
                self.send_response(status)
                self.send_header("Content-Type", "application/json")
                self.send_header("Content-Length", str(len(body)))
                self.end_headers()
                self.wfile.write(body)

            def _check_auth(self, webhook) -> Optional[Dict[str, Any]]:
                if not webhook.secret:
                    return None
                secret = ""
                if "Authorization" in self.headers:
                    secret = self.headers.get("Authorization", "").strip()
                if not secret and "X-Webhook-Secret" in self.headers:
                    secret = self.headers.get("X-Webhook-Secret", "").strip()
                if secret != self._allowed_secret:
                    return {"success": False, "error": "forbidden"}

                signature = self.headers.get("X-Webhook-Signature", "")
                timestamp = self.headers.get("X-Webhook-Timestamp", "")
                if signature and timestamp:
                    length = int(self.headers.get("Content-Length", 0))
                    body = self.rfile.read(length) if length else b""
                    if not _verify_signature(self._allowed_secret, timestamp, signature, body):
                        return {"success": False, "error": "forbidden"}
                return None

            def do_GET(self):
                paths = {w.path: w for w in trigger._webhooks.values() if w.enabled}
                webhook = paths.get(self.path)
                if not webhook:
                    self._send_json(404, {"success": False, "error": "not found"})
                    return
                auth_error = self._check_auth(webhook)
                if auth_error:
                    self._send_json(403, auth_error)
                    return
                result = trigger.trigger(webhook.id)
                self._send_json(200, result)

            def do_POST(self):
                paths = {w.path: w for w in trigger._webhooks.values() if w.enabled}
                webhook = paths.get(self.path)
                if not webhook:
                    self._send_json(404, {"success": False, "error": "not found"})
                    return
                auth_error = self._check_auth(webhook)
                if auth_error:
                    self._send_json(403, auth_error)
                    return
                length = int(self.headers.get("Content-Length", 0))
                payload = {}
                if length:
                    try:
                        payload = json.loads(self.rfile.read(length).decode("utf-8"))
                    except Exception:
                        pass
                result = trigger.trigger(webhook.id, payload=payload)
                self._send_json(200, result)

        server = HTTPServer((host, port), Handler)
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        logger.info("webhook server started on %s:%d", host, port)
        return thread

    def _save(self, webhook: Webhook) -> None:
        try:
            (_WEBHOOK_DIR / f"{webhook.id}.json").write_text(
                json.dumps(webhook.to_dict(), ensure_ascii=False, indent=2),
                encoding="utf-8",
            )
        except Exception:
            pass


webhook_trigger = WebhookTrigger()
