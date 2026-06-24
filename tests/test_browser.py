"""
PRISM Agent - 浏览器测试套件
覆盖：打开网页、读取快照、关闭浏览器
"""

import os
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from prism.tools.browser_bridge import open_page, page_snapshot, close_browser


def test_open_example_dot_com():
    result = open_page("https://example.com", headless=True)
    assert result.get("success") is True
    assert "example.com" in (result.get("url") or "")


def test_snapshot_after_open():
    open_result = open_page("https://example.com", headless=True)
    assert open_result.get("success") is True

    snap = page_snapshot()
    assert snap.get("success") is True
    title = snap.get("title") or ""
    content = snap.get("content") or ""
    assert "Example Domain" in title or "Example Domain" in content


def test_close_browser():
    close = close_browser()
    assert close.get("success") is True
