"""E2E verification for PRISM Agent desktop path.
Reusable as script or module. Masks secrets before logging.
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import time
from pathlib import Path
from typing import Any, Optional


REPO_ROOT = Path(r"C:\Users\zd\prism")
DESKTOP_SETTINGS = Path.home() / ".prism" / "desktop_settings.json"
LOG_PATH = REPO_ROOT / "e2e_verify.log"


def mask_secret(value: Any) -> Any:
    if isinstance(value, str) and len(value) >= 8:
        return value[:4] + "****" + value[-4:]
    return value


def log(msg: str, *, quiet: bool = False) -> None:
    line = f"[{time.strftime('%H:%M:%S')}] {msg}"
    if not quiet:
        print(line, flush=True)
    try:
        with LOG_PATH.open("a", encoding="utf-8") as f:
            f.write(line + "\n")
    except Exception:
        pass


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        prog="e2e_verify",
        description="PRISM Agent E2E verification: config -> agent -> memory -> chat.",
    )
    parser.add_argument(
        "--settings",
        default=str(DESKTOP_SETTINGS),
        help="Path to desktop_settings.json (default: ~/.prism/desktop_settings.json)",
    )
    parser.add_argument(
        "--question",
        default="请用一句话回复：请只回复 E2E_OK。",
        help="Question sent to the agent (default: '请用一句话回复：请只回复 E2E_OK。')",
    )
    parser.add_argument(
        "--quiet",
        action="store_true",
        help="Suppress stdout; still append to e2e_verify.log",
    )
    parser.add_argument(
        "--log-path",
        default=str(LOG_PATH),
        help="Log file path (default: <repo>/e2e_verify.log)",
    )
    return parser.parse_args()


def _load_settings(path: Path) -> dict:
    if not path.exists():
        raise FileNotFoundError(f"desktop settings not found: {path}")
    return json.loads(path.read_text(encoding="utf-8"))


def _apply_settings(settings: dict, *, quiet: bool = False) -> None:
    from prism.config import get_config

    model_key = settings.get("model") or ""
    provider = settings.get("provider") or ""
    base_url = settings.get("base_url") or ""
    api_key = settings.get("api_key") or ""

    get_config().set("model.provider", provider)
    get_config().set("model.base_url", base_url)
    get_config().set("model.default", model_key)
    get_config().set("model.api_key", api_key)
    log(f"settings applied provider={provider} base_url={base_url} model={model_key}", quiet=quiet)


def _warm_memory(*, quiet: bool = False) -> None:
    from prism.memory import persistent_memory

    try:
        persistent_memory.remember("e2e_verify_user", "贾总", category="user_profile")
        log("memory: wrote user_profile", quiet=quiet)
        ctx = persistent_memory.get_context(max_items=3, scope="default")
        log(f"memory: context={ctx[:120].replace(chr(10), ' ')}", quiet=quiet)
    except Exception as exc:
        log(f"memory: skipped warmup={exc}", quiet=quiet)


def _chat(agent: Any, question: str, *, quiet: bool = False) -> str:
    log(f"send message: {question}", quiet=quiet)
    start = time.time()
    result = agent.chat(question)
    elapsed = time.time() - start
    log(f"chat result type={type(result).__name__} len={len(str(result))} time={elapsed:.2f}s", quiet=quiet)
    log(f"chat result preview: {str(result)[:240].replace(chr(10), ' ')}", quiet=quiet)
    return result


def _normalize_result(result: Any) -> str:
    if isinstance(result, str):
        return result
    if isinstance(result, dict):
        if result.get("content"):
            return str(result.get("content"))
        if result.get("success") and result.get("result"):
            return str(result.get("result"))
    return ""


def run(settings_path: Optional[str] = None, question: str = "", *, quiet: bool = False, log_path: Optional[str] = None) -> int:
    global LOG_PATH
    if log_path:
        LOG_PATH = Path(log_path)

    settings_path = Path(settings_path or DESKTOP_SETTINGS)
    if not question:
        question = "请用一句话回复：请只回复 E2E_OK。"

    try:
        settings = _load_settings(settings_path)
    except Exception as exc:
        log(f"ERROR: {exc}", quiet=quiet)
        return 2

    masked = {k: mask_secret(v) if isinstance(v, str) else v for k, v in settings.items()}
    log(f"desktop_settings={masked}", quiet=quiet)

    from prism.agent import create_agent

    _apply_settings(settings, quiet=quiet)

    agent = create_agent()
    log(f"agent created memory_scope={agent.memory_scope}", quiet=quiet)

    _warm_memory(quiet=quiet)

    result = _chat(agent, question, quiet=quiet)
    text = _normalize_result(result).strip()

    if not text:
        log("ERROR: chat returned empty/error", quiet=quiet)
        return 3

    log("E2E verification passed", quiet=quiet)
    return 0


def main() -> int:
    args = parse_args()
    return run(
        settings_path=args.settings,
        question=args.question,
        quiet=args.quiet,
        log_path=args.log_path,
    )


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as exc:
        log(f"ERROR: unhandled={exc}")
        raise SystemExit(4)
