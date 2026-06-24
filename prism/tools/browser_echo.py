"""
PRISM Agent - 浏览器回显服务
把浏览器能力包装成本地服务，方便后续 Gateway/CLI 调用
"""

import logging
from typing import Any, Dict, Optional

logger = logging.getLogger(__name__)

try:
    from prism.tools.browser_bridge import open_page, page_snapshot, close_browser
    _HAS_BROWSER = True
except Exception as exc:
    logger.debug("browser echo service import failed: %s", exc)
    _HAS_BROWSER = False


class BrowserEchoService:
    def open(self, url: str, headless: bool = True) -> Dict[str, Any]:
        if not _HAS_BROWSER:
            return {"success": False, "error": "browser unavailable"}
        return open_page(url, headless=headless)

    def snapshot(self) -> Dict[str, Any]:
        if not _HAS_BROWSER:
            return {"success": False, "error": "browser unavailable"}
        return page_snapshot()

    def close(self) -> Dict[str, Any]:
        if not _HAS_BROWSER:
            return {"success": True, "message": "skipped"}
        return close_browser()


browser_echo = BrowserEchoService()
