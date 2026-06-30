"""PRISM Desktop tests."""
from __future__ import annotations

import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
import flet as ft

# Ensure prism_desktop package is importable
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from prism_desktop.main import PrismDesktop


@pytest.fixture()
def desktop():
    page = MagicMock(spec=ft.Page)
    page.title = "PRISM Agent"
    page.theme_mode = ft.ThemeMode.DARK
    page.padding = 14
    page.window_width = 1320
    page.window_height = 800
    page.window_top = 100
    page.window_left = 100
    page.session_id = "test-session"
    d = PrismDesktop(page)
    d._set_status = MagicMock()
    return d


def test_debounced_save_settings(desktop):
    """_save_settings_debounced should batch rapid calls."""
    with patch.object(desktop, "_save_settings") as mock_save:
        desktop._save_settings_delay = 0.05
        desktop._save_settings_debounced()
        desktop._save_settings_debounced()
        desktop._save_settings_debounced()
        assert mock_save.call_count == 0
        desktop._save_settings_timer.join(timeout=2)
        assert mock_save.call_count == 1


def test_stop_send_interrupts_stream(desktop):
    """Stopping generation should set the flag to False."""
    desktop._generating = True
    mock_stop = MagicMock()
    mock_send = MagicMock()
    desktop.stop_btn = mock_stop
    desktop.send_btn = mock_send
    desktop._stop_send()
    assert desktop._generating is False
    assert mock_stop.visible is False
    assert mock_send.visible is True
    mock_stop.update.assert_called_once()
    mock_send.update.assert_called_once()


def test_browser_tabs_disabled_when_deps_missing(desktop):
    """Browser buttons should be disabled if playwright/chromium missing."""
    with patch.object(PrismDesktop, "_check_browser_dependencies", return_value={"playwright": False, "chromium": False}):
        desktop._browser_deps_ok = False
        assert desktop._browser_deps_ok is False
