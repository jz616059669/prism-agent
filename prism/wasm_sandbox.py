"""
PRISM Agent - WASM 沙盒
支持 WebAssembly 运行时，可运行 Rust/Go 产物
无 WASM 运行时则降级为提示
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, Optional

logger = logging.getLogger(__name__)


@dataclass
class WasmRunResult:
    success: bool
    output: str = ""
    error: str = ""


class WasmSandbox:
    def __init__(self) -> None:
        self._runtime = self._detect_runtime()

    def _detect_runtime(self) -> Optional[str]:
        candidates = ["wasmtime", "wasmer", "wamr", "wasm3"]
        import shutil
        for candidate in candidates:
            if shutil.which(candidate):
                return candidate
        return None

    def run(self, wasm_path: str, args: Optional[list[str]] = None) -> WasmRunResult:
        result = WasmRunResult(success=False)
        if not self._runtime:
            result.error = "未检测到 WASM 运行时（wasmtime/wasmer/wamr/wasm3），请先安装。"
            return result
        wasm_file = Path(wasm_path)
        if not wasm_file.exists():
            result.error = f"WASM 文件不存在: {wasm_path}"
            return result
        try:
            import subprocess
            cmd = [self._runtime, str(wasm_file)] + (args or [])
            proc = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
            result.success = proc.returncode == 0
            result.output = proc.stdout
            result.error = proc.stderr
        except Exception as exc:
            result.error = str(exc)
        return result


wasm_sandbox = WasmSandbox()
