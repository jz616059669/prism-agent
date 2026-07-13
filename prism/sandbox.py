"""
PRISM Agent - Code Interpreter Sandbox
安全执行 Python，支持 matplotlib 图表直接嵌入对话
"""

from __future__ import annotations

import base64
import builtins
import io
import logging
import os
import sys
import threading
from pathlib import Path
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)

_SANDBOX_DIR = Path.home() / ".prism" / "sandbox"
_SANDBOX_DIR.mkdir(parents=True, exist_ok=True)

_ALLOWED_MODULES = {
    "math", "statistics", "random", "datetime", "json", "re", "collections",
    "itertools", "functools", "pathlib", "typing", "dataclasses", "decimal",
    "fractions", "string", "textwrap", "pprint", "copy", "time",
    "matplotlib", "matplotlib.pyplot", "numpy", "pandas",
}


def _safe_import(name: str, globals=None, locals=None, fromlist=(), level=0):
    root = name.split(".")[0]
    if root in _ALLOWED_MODULES or any(name.startswith(m + ".") for m in _ALLOWED_MODULES):
        return builtins.__import__(name, globals, locals, fromlist, level)
    raise ImportError(f"Module '{name}' is not allowed in sandbox")


class _SafeBuiltins:
    def __getattr__(self, name: str) -> Any:
        if name in {"open", "exec", "eval", "compile", "__import__", "breakpoint",
                     "exit", "quit", "help", "input", "getattr", "setattr", "delattr",
                     "globals", "locals", "vars", "dir"}:
            raise AttributeError(name)
        return getattr(builtins, name)

    def __import__(self, name, globals=None, locals=None, fromlist=(), level=0):
        return _safe_import(name, globals, locals, fromlist, level)

    def __getitem__(self, name: str) -> Any:
        if name in {"open", "exec", "eval", "compile", "__import__", "breakpoint",
                     "exit", "quit", "help", "input", "getattr", "setattr", "delattr",
                     "globals", "locals", "vars", "dir"}:
            raise KeyError(name)
        return getattr(builtins, name)


def _make_safe_globals() -> Dict[str, Any]:
    builtins_dict = {k: v for k, v in builtins.__dict__.items() if k not in {"open", "exec", "eval", "compile", "__import__", "breakpoint", "exit", "quit", "help", "input", "getattr", "setattr", "delattr", "globals", "locals", "vars", "dir"}}
    builtins_dict["__import__"] = _safe_import
    return {"__builtins__": builtins_dict, "__name__": "__sandbox__"}


def run_sandbox(code: str, timeout: int = 30) -> Dict[str, Any]:
    result: Dict[str, Any] = {"success": False, "output": "", "plots": [], "error": ""}
    if not code.strip():
        result["success"] = True
        return result

    def _bg() -> None:
        globals_dict = _make_safe_globals()
        old_cwd = Path.cwd()
        try:
            os.environ.setdefault("MPLBACKEND", "Agg")
            os.chdir(str(_SANDBOX_DIR))
            try:
                import matplotlib
                try:
                    import matplotlib.pyplot as plt
                    plt.close("all")
                except Exception:
                    pass
            except Exception:
                pass
            try:
                out = io.StringIO()
                sys.stdout = out
                exec(code, globals_dict)
                result["output"] = out.getvalue()
                result["success"] = True
            except Exception as exc:  # noqa: BLE001
                result["error"] = str(exc)
            finally:
                sys.stdout = sys.__stdout__
            figs: List[Any] = []
            try:
                import matplotlib.pyplot as plt
                figs = [plt.figure(n) for n in plt.get_fignums()]
            except Exception:
                pass
            for fig in figs[:10]:
                buf = io.BytesIO()
                try:
                    fig.savefig(buf, format="png", bbox_inches="tight", dpi=150)
                    buf.seek(0)
                    result["plots"].append("data:image/png;base64," + base64.b64encode(buf.read()).decode("ascii"))
                except Exception:
                    pass
                try:
                    import matplotlib.pyplot as plt
                    plt.close(fig)
                except Exception:
                    pass
        finally:
            try:
                os.chdir(str(old_cwd))
            except Exception:
                pass

    try:
        t = threading.Thread(target=_bg, daemon=True)
        t.start()
        t.join(timeout=timeout)
        if t.is_alive():
            result["error"] = f"Execution timed out after {timeout}s"
            result["success"] = False
    except Exception as exc:  # noqa: BLE001
        result["error"] = str(exc)
    return result
