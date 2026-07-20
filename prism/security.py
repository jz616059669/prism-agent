"""
PRISM Agent - 安全与审计
工具风险分级、危险操作拦截、审计日志。
"""
from __future__ import annotations

import json
import logging
import threading
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional

logger = logging.getLogger("prism.security")

_AUDIT_DIR = Path.home() / ".prism" / "audit"
_AUDIT_DIR.mkdir(parents=True, exist_ok=True)

DANGEROUS_TOOLS = {
    "execute_tool",
    "run_terminal",
    "web_search",
    "browser",
    "file_write",
    "file_patch",
}

HIGH_RISK_COMMANDS = [
    "rm ", "del ", "rmdir", "rm -rf", "rm -fr",
    "shutdown", "reboot", "reboot", "format",
    "mkfs", "dd ", "sudo", "su ", "chmod 777",
    "curl | bash", "wget | bash", "powershell",
    "cmd.exe", "reg delete", "reg add",
]


@dataclass
class AuditRecord:
    ts: str
    tool: str
    args: Dict[str, Any]
    success: bool
    error: Optional[str] = None
    user: str = ""


class SecurityManager:
    """安全与审计管理器"""

    def __init__(self, audit_enabled: bool = True):
        self._lock = threading.Lock()
        self._audit_enabled = audit_enabled
        self._blocked: List[str] = []

    def check(self, tool_name: str, kwargs: Dict[str, Any], user: str = "") -> Optional[str]:
        """检查是否允许执行；返回错误信息则拦截，返回 None 则放行"""
        if tool_name not in DANGEROUS_TOOLS:
            return None
        command = self._extract_command(tool_name, kwargs)
        if not command:
            return None
        for risk in HIGH_RISK_COMMANDS:
            if risk in command.lower():
                msg = f"安全拦截：工具 {tool_name} 包含高危命令 `{risk}`"
                logger.warning("%s | command=%s user=%s", msg, command, user)
                self._audit(tool_name, kwargs, success=False, error=msg, user=user)
                return msg
        return None

    def audit(self, tool_name: str, kwargs: Dict[str, Any], success: bool, error: Optional[str] = "", user: str = "") -> None:
        if not self._audit_enabled:
            return
        self._audit(tool_name, kwargs, success, error, user)

    def _audit(self, tool_name: str, kwargs: Dict[str, Any], success: bool, error: Optional[str], user: str) -> None:
        try:
            record = AuditRecord(
                ts=datetime.now().isoformat(),
                tool=tool_name,
                args=_safe_args(kwargs),
                success=success,
                error=error or "",
                user=user,
            )
            path = _AUDIT_DIR / f"{datetime.now().strftime('%Y%m%d')}.jsonl"
            with self._lock:
                with open(path, "a", encoding="utf-8") as f:
                    f.write(json.dumps(record.__dict__, ensure_ascii=False) + "\n")
        except Exception:
            logger.debug("audit write failed", exc_info=True)

    @staticmethod
    def _extract_command(tool_name: str, kwargs: Dict[str, Any]) -> str:
        if tool_name in {"execute_tool", "run_terminal"}:
            return str(kwargs.get("command") or kwargs.get("text") or "")
        if tool_name == "web_search":
            return str(kwargs.get("query") or "")
        if tool_name == "browser":
            return str(kwargs.get("url") or kwargs.get("action") or "")
        if tool_name in {"file_write", "file_patch"}:
            return str(kwargs.get("path") or "") + " " + str(kwargs.get("content") or kwargs.get("text") or "")
        return ""


def _safe_args(kwargs: Dict[str, Any]) -> Dict[str, Any]:
    out = {}
    for k, v in kwargs.items():
        if any(s in k.lower() for s in ["secret", "token", "password", "api_key"]):
            out[k] = "***"
        else:
            out[k] = v
    return out


security_manager = SecurityManager()
