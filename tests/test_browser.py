"""浏览器集成测试"""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

from prism.tools.browser import browser


def test_browser_navigate():
    browser.navigate("https://example.com", headless=True)
    snap = browser.snapshot(full=False)
    assert snap["success"] is True
    assert "Example Domain" in snap.get("content", "")
    browser.disconnect()


def test_browser_snapshot():
    browser.navigate("https://example.com", headless=True)
    snap = browser.snapshot(full=False)
    assert snap["success"] is True
    assert "Example Domain" in snap.get("content", "")
    browser.disconnect()
