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
    "file_read",
    "terminal",
    "code_execution",
}

HIGH_RISK_COMMANDS = [
    # Linux/macOS
    "rm ", "del ", "rmdir", "rm -rf", "rm -fr",
    "shutdown", "reboot", "format", "mkfs", "dd ",
    "sudo ", "su ", "chmod 777", "chown ",
    "curl | bash", "wget | bash",
    "python -c", "python3 -c", "perl -e", "ruby -e",
    "eval ", "exec ", ":(){", "fork bomb",
    "> /dev/", ">/dev/", "2>/dev/",
    # Windows
    "powershell", "cmd.exe", "cmd /c", "reg delete", "reg add",
    "net user ", "net localgroup", "net stop ", "net start ",
    "sc delete", "sc stop", "taskkill /f", "wmic",
    "rundll32", "mshta", "certutil -decode", "bitsadmin",
    "schtasks /create", "schtasks /delete",
    "wusa.exe", "msiexec", "bcdedit", "diskpart",
    "format c:", "format d:",
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
    
    def __init__(self, audit_enabled: bool = True, confirm_dangerous: bool = True):
        self._lock = threading.Lock()
        self._audit_enabled = audit_enabled
        self._confirm_dangerous = confirm_dangerous
        self._blocked: List[str] = []
        self._pending_confirm: Dict[str, Dict[str, Any]] = {}
        self._allowed_dirs: List[str] = []
        self._blocked_dirs: List[str] = []
        self._max_file_size: int = 10 * 1024 * 1024  # 10MB
    
    def configure(self, allowed_dirs: Optional[List[str]] = None, blocked_dirs: Optional[List[str]] = None, max_file_size: Optional[int] = None) -> None:
        """配置安全策略"""
        if allowed_dirs is not None:
            self._allowed_dirs = [str(Path(d).resolve()) for d in allowed_dirs]
        if blocked_dirs is not None:
            self._blocked_dirs = [str(Path(d).resolve()) for d in blocked_dirs]
        if max_file_size is not None:
            self._max_file_size = max_file_size
    
    def check(self, tool_name: str, kwargs: Dict[str, Any], user: str = "") -> Optional[str]:
        """
        检查是否允许执行；返回错误信息则拦截，返回 None 则放行。
        高危命令返回 'CONFIRM_REQUIRED' 表示需要人工确认。
        """
        if tool_name not in DANGEROUS_TOOLS:
            return None
        command = self._extract_command(tool_name, kwargs)
        if not command:
            return None
        
        # 文件访问控制
        if tool_name in {"file_read", "file_write", "file_patch"}:
            raw_path = kwargs.get("path") or kwargs.get("file_path") or ""
            try:
                resolved = str(Path(raw_path).resolve())
            except (OSError, ValueError):
                resolved = str(raw_path)
            if self._allowed_dirs:
                if not any(resolved.startswith(d) for d in self._allowed_dirs):
                    msg = f"安全拦截：文件路径不在允许目录内: {raw_path}"
                    logger.warning(msg)
                    self._audit(tool_name, kwargs, success=False, error=msg, user=user)
                    return msg
            for blocked in self._blocked_dirs:
                try:
                    blocked_resolved = str(Path(blocked).resolve())
                except (OSError, ValueError):
                    blocked_resolved = blocked
                if resolved.startswith(blocked_resolved):
                    msg = f"安全拦截：文件路径在禁止目录内: {raw_path}"
                    logger.warning(msg)
                    self._audit(tool_name, kwargs, success=False, error=msg, user=user)
                    return msg
            
            # 文件大小检查
            if tool_name in {"file_write", "file_patch"}:
                content = kwargs.get("content") or kwargs.get("text") or ""
                if len(content.encode("utf-8")) > self._max_file_size:
                    msg = f"安全拦截：文件内容超过大小限制 {self._max_file_size} bytes"
                    logger.warning(msg)
                    self._audit(tool_name, kwargs, success=False, error=msg, user=user)
                    return msg
        
        blocked_risks = []
        confirm_risks = []
        for risk in HIGH_RISK_COMMANDS:
            if risk in command.lower():
                if risk in {"rm ", "del ", "rmdir", "rm -rf", "rm -fr", "format", "mkfs", "dd ", "chmod 777", "reg delete", "reg add", "format c:", "format d:"}:
                    confirm_risks.append(risk)
                else:
                    blocked_risks.append(risk)
        
        if blocked_risks:
            msg = f"安全拦截：工具 {tool_name} 包含高危命令 `{blocked_risks[0]}`"
            logger.warning("%s | command=%s user=%s", msg, command, user)
            self._audit(tool_name, kwargs, success=False, error=msg, user=user)
            self._blocked.append(msg)
            return msg
        
        if confirm_risks:
            msg = f"CONFIRM_REQUIRED：工具 {tool_name} 包含需确认命令 `{confirm_risks[0]}`"
            logger.warning("%s | command=%s user=%s", msg, command, user)
            self._audit(tool_name, kwargs, success=False, error=msg, user=user)
            self._pending_confirm[tool_name] = {"kwargs": kwargs, "command": command, "user": user, "risk": confirm_risks[0]}
            return msg
        
        return None
    
    def confirm(self, tool_name: str) -> bool:
        """确认一个待审核的工具调用"""
        pending = self._pending_confirm.pop(tool_name, None)
        if not pending:
            return False
        logger.info("user confirmed dangerous tool: %s command=%s", tool_name, pending["command"])
        return True
    
    def deny(self, tool_name: str) -> None:
        """拒绝一个待审核的工具调用"""
        self._pending_confirm.pop(tool_name, None)
    
    def pending_count(self) -> int:
        """当前待确认数"""
        return len(self._pending_confirm)
    
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
        if tool_name in {"execute_tool", "run_terminal", "terminal"}:
            return str(kwargs.get("command") or kwargs.get("text") or "")
        if tool_name == "web_search":
            return str(kwargs.get("query") or "")
        if tool_name == "browser":
            return str(kwargs.get("url") or kwargs.get("action") or "")
        if tool_name in {"file_write", "file_patch"}:
            return str(kwargs.get("path") or "") + " " + str(kwargs.get("content") or kwargs.get("text") or "")
        if tool_name == "file_read":
            return str(kwargs.get("path") or "")
        if tool_name == "code_execution":
            return str(kwargs.get("code") or "")
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
