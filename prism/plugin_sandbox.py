"""
PRISM Agent - Plugin 沙盒隔离
技能运行在独立进程/容器，crash 不扩散
"""

from __future__ import annotations

import json
import logging
import os
import subprocess
import sys
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)

_SANDBOX_DIR = Path.home() / ".prism" / "plugin_sandbox"
_SANDBOX_DIR.mkdir(parents=True, exist_ok=True)


@dataclass
class PluginRunResult:
    plugin: str = ""
    success: bool = False
    output: str = ""
    error: str = ""
    duration_ms: float = 0.0

    def to_dict(self) -> Dict[str, Any]:
        return {
            "plugin": self.plugin,
            "success": self.success,
            "output": self.output,
            "error": self.error,
            "duration_ms": self.duration_ms,
        }


class PluginSandbox:
    def __init__(self, python: Optional[str] = None) -> None:
        self.python = python or sys.executable

    def run(self, plugin_name: str, input_data: Optional[Dict[str, Any]] = None, timeout: int = 30) -> PluginRunResult:
        result = PluginRunResult(plugin=plugin_name)
        plugin_file = _SANDBOX_DIR / f"{plugin_name}.py"
        if not plugin_file.exists():
            result.error = f"plugin not found: {plugin_file}"
            return result
        start = time.perf_counter()
        try:
            env = os.environ.copy()
            env["PRISM_PLUGIN_INPUT"] = json.dumps(input_data or {})
            proc = subprocess.run(
                [self.python, str(plugin_file)],
                capture_output=True,
                text=True,
                timeout=timeout,
                env=env,
                cwd=str(_SANDBOX_DIR),
            )
            result.output = proc.stdout
            result.error = proc.stderr
            result.success = proc.returncode == 0
        except subprocess.TimeoutExpired:
            result.error = "timeout"
            result.success = False
        except Exception as exc:
            result.error = str(exc)
            result.success = False
        result.duration_ms = (time.perf_counter() - start) * 1000.0
        return result

    def install_plugin(self, plugin_name: str, source_code: str) -> bool:
        try:
            (_SANDBOX_DIR / f"{plugin_name}.py").write_text(source_code, encoding="utf-8")
            return True
        except Exception:
            return False

    def uninstall_plugin(self, plugin_name: str) -> bool:
        target = _SANDBOX_DIR / f"{plugin_name}.py"
        if not target.exists():
            return False
        try:
            target.unlink()
            return True
        except Exception:
            return False


plugin_sandbox = PluginSandbox()
