"""
PRISM Agent - 自动更新检查
PyPI/GitHub 新版本检测
"""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)

_UPDATE_DIR = Path.home() / ".prism" / "updates"
_UPDATE_DIR.mkdir(parents=True, exist_ok=True)


@dataclass
class UpdateInfo:
    source: str = ""
    current: str = ""
    latest: str = ""
    has_update: bool = False
    url: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return {
            "source": self.source,
            "current": self.current,
            "latest": self.latest,
            "has_update": self.has_update,
            "url": self.url,
        }


class UpdateChecker:
    def __init__(self, current_version: str = "") -> None:
        self.current_version = current_version or __import__("prism").__version__

    def check_pypi(self, package: str = "prism-agent") -> UpdateInfo:
        info = UpdateInfo(source="pypi", current=self.current_version)
        try:
            import urllib.request
            url = f"https://pypi.org/pypi/{package}/json"
            with urllib.request.urlopen(url, timeout=15) as resp:
                data = json.loads(resp.read().decode("utf-8"))
            latest = data.get("info", {}).get("version", "")
            info.latest = latest
            info.has_update = latest and latest != self.current_version
            info.url = f"https://pypi.org/project/{package}/"
        except Exception as exc:
            logger.debug("check pypi failed: %s", exc)
        return info

    def check_github(self, repo: str = "jz616059669/prism-agent") -> UpdateInfo:
        info = UpdateInfo(source="github", current=self.current_version)
        try:
            import urllib.request
            url = f"https://api.github.com/repos/{repo}/releases/latest"
            req = urllib.request.Request(url, headers={"Accept": "application/vnd.github+json", "User-Agent": "prism-agent"})
            with urllib.request.urlopen(req, timeout=15) as resp:
                data = json.loads(resp.read().decode("utf-8"))
            latest = str(data.get("tag_name", "") or "").lstrip("v")
            info.latest = latest
            info.has_update = latest and latest != self.current_version
            info.url = data.get("html_url", "")
        except Exception as exc:
            logger.debug("check github failed: %s", exc)
        return info

    def check_all(self) -> List[Dict[str, Any]]:
        results = [self.check_pypi(), self.check_github()]
        try:
            (_UPDATE_DIR / "last_check.json").write_text(
                json.dumps([r.to_dict() for r in results], ensure_ascii=False, indent=2),
                encoding="utf-8",
            )
        except Exception:
            pass
        return [r.to_dict() for r in results]


update_checker = UpdateChecker()
