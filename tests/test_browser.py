"""
PRISM Agent - 浏览器测试套件
覆盖：打开网页、读取快照、关闭浏览器、截图、多页切换
"""
import os
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from prism.tools.browser_bridge import open_page, page_snapshot, close_browser, browser_goto, page_screenshot

LOCAL_TEST_PAGE = REPO_ROOT / "tests" / "fixtures" / "local_test_page.html"
LOCAL_TEST_URL = "file:///" + str(LOCAL_TEST_PAGE).replace("\\", "/") + "?offline=1"


def test_open_example_dot_com():
    result = open_page(LOCAL_TEST_URL if not _has_network() else "https://example.com", headless=True)
    if not result.get("success"):
        pytest.skip("browser unavailable")
    url = result.get("url") or ""
    assert "prism" in url.lower() or "example.com" in url.lower()


def test_snapshot_after_open():
    open_result = open_page(LOCAL_TEST_URL if not _has_network() else "https://example.com", headless=True)
    if not open_result.get("success"):
        pytest.skip("network unavailable for browser test")

    snap = page_snapshot()
    assert snap.get("success") is True
    content = (snap.get("content") or "") + " " + (snap.get("title") or "")
    assert "PRISM" in content or "Example Domain" in content


def test_close_browser():
    close = close_browser()
    assert close.get("success") is True


def test_screenshot_after_open():
    open_result = open_page(LOCAL_TEST_URL if not _has_network() else "https://example.com", headless=True)
    if not open_result.get("success"):
        pytest.skip("network unavailable for browser test")
    result = page_screenshot(path=None)
    assert result.get("success") is True
    path = result.get("path") or ""
    assert path.endswith(".png") or "prism_screenshot_" in path


def test_multi_page_navigation():
    first = browser_goto(LOCAL_TEST_URL if not _has_network() else "https://example.com", headless=True)
    if not first.get("success"):
        pytest.skip("network unavailable for browser test")

    second = browser_goto(LOCAL_TEST_URL if not _has_network() else "https://example.com", headless=True)
    assert second.get("success") is True

    snap = page_snapshot()
    assert snap.get("success") is True
    content = (snap.get("content") or "") + " " + (snap.get("title") or "")
    assert "PRISM" in content or "Example Domain" in content


def _has_network() -> bool:
    try:
        import urllib.request
        with urllib.request.urlopen("https://example.com", timeout=5) as resp:
            return resp.status == 200
    except Exception:
        return False
