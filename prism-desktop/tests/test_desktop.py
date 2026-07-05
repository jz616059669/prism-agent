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
    with patch.object(PrismDesktop, "_set_status", MagicMock()), \
         patch.object(PrismDesktop, "_append_terminal", MagicMock()), \
         patch.object(PrismDesktop, "_append_mcp", MagicMock()), \
         patch.object(PrismDesktop, "_apply_theme", MagicMock()), \
         patch.object(PrismDesktop, "_build_ui", MagicMock()), \
         patch.object(PrismDesktop, "_bind_context_menu", MagicMock()), \
         patch.object(PrismDesktop, "_bind_tray", MagicMock()), \
         patch.object(PrismDesktop, "_maybe_show_setup_wizard", MagicMock()), \
         patch.object(PrismDesktop, "_start_update_check", MagicMock()), \
         patch("prism_desktop.main.create_agent", return_value=MagicMock()):
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


def test_run_terminal_command_calls_subprocess(desktop):
    """_run_terminal_command should execute shell command."""
    with patch.object(desktop, "_append_terminal") as mock_terminal, \
         patch.object(desktop, "_append_mcp") as mock_mcp, \
         patch("prism_desktop.main.subprocess.run") as mock_run:
        mock_run.return_value.stdout = "hello"
        mock_run.return_value.stderr = ""
        desktop.terminal_input = MagicMock()
        desktop.terminal_input.value = "echo hello"
        desktop._run_terminal_command()
        mock_run.assert_called_once()
        assert mock_terminal.call_count >= 1
        mock_mcp.assert_called_once()


def test_startup_create_agent_failure_sets_agent_none():
    """When create_agent raises, desktop should set agent to None."""
    with patch.object(PrismDesktop, "_set_status", MagicMock()), \
         patch.object(PrismDesktop, "_append_terminal", MagicMock()), \
         patch("prism_desktop.main.create_agent", side_effect=RuntimeError("boom")):
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
        assert d.agent is None


def test_init_fallback_shows_retry_and_log(monkeypatch):
    """Init failure should set init error and show banner in main UI."""
    from prism_desktop.main import PrismDesktop

    with patch.object(PrismDesktop, "_set_status", MagicMock()), \
         patch.object(PrismDesktop, "_append_terminal", MagicMock()), \
         patch("prism_desktop.main.create_agent", side_effect=RuntimeError("boom")), \
         patch.object(PrismDesktop, "_build_ui", MagicMock()), \
         patch.object(PrismDesktop, "_bind_context_menu", MagicMock()), \
         patch.object(PrismDesktop, "_bind_tray", MagicMock()), \
         patch.object(PrismDesktop, "_maybe_show_setup_wizard", MagicMock()), \
         patch.object(PrismDesktop, "_load_settings", return_value={}), \
         patch.object(PrismDesktop, "_start_update_check", MagicMock()):
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
        assert d.agent is None
        assert d._init_error is not None
        assert isinstance(d._init_error, RuntimeError)


def test_retry_init_restores_ui(monkeypatch):
    """Retry init should rebuild UI instead of showing fallback."""
    from prism_desktop.main import PrismDesktop

    with patch.object(PrismDesktop, "_set_status", MagicMock()) as status_mock, \
         patch.object(PrismDesktop, "_append_terminal", MagicMock()), \
         patch.object(PrismDesktop, "_show_init_fallback") as mock_fallback, \
         patch.object(PrismDesktop, "_build_ui", MagicMock()) as build_mock, \
         patch.object(PrismDesktop, "_bind_context_menu", MagicMock()), \
         patch.object(PrismDesktop, "_bind_tray", MagicMock()), \
         patch.object(PrismDesktop, "_maybe_show_setup_wizard", MagicMock()), \
         patch.object(PrismDesktop, "_load_settings", return_value={}), \
         patch.object(PrismDesktop, "_start_update_check", MagicMock()), \
         patch.object(PrismDesktop, "_save_settings", MagicMock()), \
         patch.object(PrismDesktop, "_apply_settings", MagicMock()):
        d = PrismDesktop.__new__(PrismDesktop)
        d.page = MagicMock(spec=ft.Page)
        d._settings = {}
        d._retry_init()
        build_mock.assert_called_once()
        mock_fallback.assert_not_called()
        status_mock.assert_called_once()
