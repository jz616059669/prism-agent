"""
PRISM Agent - 浏览器工具桥接
修复浏览器测试与 CLI/Gateway 的集成
"""

import logging
from typing import Any, Dict, Optional

logger = logging.getLogger(__name__)

try:
    from prism.tools.browser import browser as browser_api
    _HAS_BROWSER = True
except Exception as exc:
    logger.debug("browser bridge import failed: %s", exc)
    _HAS_BROWSER = False


def open_page(url: str, headless: bool = True) -> Dict[str, Any]:
    if not _HAS_BROWSER:
        return {"success": False, "error": "browser module unavailable"}
    return browser_api.navigate(url, headless=headless)


def page_snapshot() -> Dict[str, Any]:
    if not _HAS_BROWSER:
        return {"success": False, "error": "browser module unavailable"}
    return browser_api.snapshot(full=False)


def close_browser() -> Dict[str, Any]:
    if not _HAS_BROWSER:
        return {"success": True, "message": "browser unavailable, skipped"}
    return browser_api.disconnect()
