"""最小浏览器集成测试"""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

import pytest
from prism.tools.browser import browser


@pytest.fixture(scope="module")
def live_browser():
    browser.navigate("https://example.com", headless=True)
    yield browser
    browser.disconnect()


def test_navigate_success(live_browser):
    result = live_browser.navigate("https://example.com", headless=True)
    assert result.get("success") is True


def test_snapshot_contains_title(live_browser):
    snap = live_browser.snapshot(full=False)
    assert snap.get("success") is True
    title = snap.get("title", "")
    content = snap.get("content", "")
    assert "Example Domain" in title or "Example Domain" in content
