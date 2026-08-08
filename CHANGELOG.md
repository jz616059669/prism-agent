# Changelog

## [2.1.7] - 2026-07-26

### Changed
- **Code quality**: ruff F-level dead code removal across desktop and backend
- **Exception hardening**: narrowed bare `except Exception:` in agent.py and config.py to specific types (`json.JSONDecodeError`, `OSError`, `yaml.YAMLError`, etc.)
- **Desktop UI thread safety**: replaced `page.run_task` with thread-safe `_run_on_ui` wrapper in `main.py`, `chat.py`, `terminal.py`, `mcp.py`
- **Logging**: replaced `traceback.format_exc()` with `exc_info=True` in desktop and backend for cleaner logs
- **Config watcher**: added `_safe_debug()` helper to eliminate pytest `UnhandledThreadExceptionWarning`

### Fixed
- Terminal command execution routed to dedicated background thread to avoid blocking UI event loop
- Notification and browser-skill UI updates properly marshaled back to Flet UI thread
- `test_e2e_chat_without_config_returns_config_error` now stable by clearing API keys via monkeypatch

### Added
- `prism-desktop.spec` updated to include `flet_web/web` assets for PyInstaller
- Windows desktop EXE build: `dist/PRISM.exe` (~115MB)

### DevOps
- PyPI release: https://pypi.org/project/prism-agent/2.1.7/
- GitHub master pushed
- Project folders reorganized: `docs/zh/`, `logs/`, C:\Archives\ structure
- Hermes cache cleaned without touching config/state/runtime files

## [2.1.6] - 2026-07-26
- Initial "perfect landing" iteration: ruff cleanup, exception tightening, py_compile pass, 168 tests green
