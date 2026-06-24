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
    result = browser_api.navigate(url, headless=headless)
    logger.info("browser open url=%s headless=%s success=%s", url, headless, result.get("success"))
    return result


def page_snapshot() -> Dict[str, Any]:
    if not _HAS_BROWSER:
        return {"success": False, "error": "browser module unavailable"}
    result = browser_api.snapshot(full=False)
    logger.info("browser snapshot success=%s title=%s", result.get("success"), result.get("title"))
    return result


def close_browser() -> Dict[str, Any]:
    if not _HAS_BROWSER:
        return {"success": True, "message": "browser unavailable, skipped"}
    result = browser_api.disconnect()
    logger.info("browser close success=%s", result.get("success"))
    return result
