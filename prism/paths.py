import os
from pathlib import Path
from typing import Optional


PRISM_HOME = Path.home() / ".prism"


def ensure_dirs() -> None:
    """Ensure prism directories exist."""
    PRISM_HOME.mkdir(parents=True, exist_ok=True)
    (PRISM_HOME / "logs").mkdir(parents=True, exist_ok=True)
    (PRISM_HOME / "sessions").mkdir(parents=True, exist_ok=True)
    (PRISM_HOME / "memory").mkdir(parents=True, exist_ok=True)
    (PRISM_HOME / "workspaces").mkdir(parents=True, exist_ok=True)


def sessions_dir() -> Path:
    ensure_dirs()
    return PRISM_HOME / "sessions"


def memory_dir() -> Path:
    ensure_dirs()
    return PRISM_HOME / "memory"


def workspaces_dir() -> Path:
    ensure_dirs()
    return PRISM_HOME / "workspaces"


def logs_dir() -> Path:
    ensure_dirs()
    return PRISM_HOME / "logs"


def session_path(name: str) -> Path:
    return sessions_dir() / f"{name}.json"


def memory_path(key: str) -> Path:
    """Return a sanitized path under memory_dir for a given key."""
    safe = "".join(c if c.isalnum() or c in "-_." else "_" for c in key)
    return memory_dir() / f"{safe}.json"


def workspace_path(name: str) -> Path:
    return workspaces_dir() / name


def config_dir() -> Path:
    return PRISM_HOME / "config"


def check_permissions() -> Optional[str]:
    """Check if prism home is writable. Return error string or None."""
    try:
        test = PRISM_HOME / ".write_test"
        test.write_text("ok", encoding="utf-8")
        test.unlink()
        return None
    except Exception as exc:  # pragma: no cover
        return str(exc)
