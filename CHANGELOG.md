# Changelog

## 2.1.0 - 2026-07-02

### Added
- Desktop client test suite (`prism-desktop/tests/test_desktop.py`) covering debounced save, stop send, browser dep check, terminal command, startup fallback
- Real backend streaming chat in desktop: `_send` now iterates provider chunks and stops on button press
- Window position/size persistence: restores geometry on restart

### Changed
- Unified version to `2.1.0` across package, packaging script, and README
- Desktop save settings debounced to 0.5s to avoid frequent disk writes

### Fixed
- Browser control now shows actionable error when `playwright` or `Chromium` is missing
- Right-side terminal/MCP tabs actually switch panels instead of being dead `on_change=lambda e: None`
- Desktop startup no longer hard-crashes when `create_agent()` or `prism_config` fails; falls back to usable empty UI
- Removed duplicate `_build_appbar`, `_toggle_sidebar`, `_cycle_theme`, `_build_ui` definitions in `main.py`
- Terminal log path initialized before `create_agent()` so startup errors are visible
- Streaming send sets `_generating` flag and respects stop button

## 0.2.1 - 2026-06-24

### Added
- Desktop client real backend connection (`prism-desktop/prism_desktop/main.py`)
- Browser control in desktop UI: open page, read snapshot, close browser
- `prism doctor` health check command
- Real model call tests (`tests/test_real_model.py`)
- Windows desktop packaging script (`scripts/build-windows.ps1`)
- Windows launcher (`scripts/build-windows.cmd`)
- Local release scripts (`scripts/release.ps1`, `scripts/release.sh`)
- PyPI release docs in README
- End-to-end verification script (`scripts/verify_e2e.py`)
- Integration tests (`tests/test_integration.py`)
- Unified logging to `~/.prism/logs/prism.log` with rotation
- `.gitignore` guard for local-only tutorials

### Changed
- Config validation now runs before model-dependent commands
- Provider pool returns clear Chinese error when no API key configured
- CLI version updated to `0.2.1`
- README/INSTALL updated with Windows desktop packaging and troubleshooting

### Fixed
- `prism config get` without key now uses `show()` correctly
- Gateway import cycle resolved
- Desktop import path handling for verification scripts

### Notes
- Video tutorial and Feishu tutorial remain local-only and are not uploaded to GitHub
- Repo remains public; local tutorials kept in working tree only
- Test suite is green on core paths
- PyPI release: `prism-agent==0.2.1` available at https://pypi.org/project/prism-agent/0.2.1/

## 0.2.0 - 2026-06-24

### Added
- Desktop client based on **Flet** (`prism-desktop/`)
- One-click installers:
  - Windows: `scripts/install.ps1`
  - macOS/Linux: `scripts/install.sh`
- Linux desktop packaging: `scripts/build-linux.sh`
- macOS desktop packaging: `scripts/build-macos.sh`
- Linux systemd service: `scripts/prism-gateway.service`
- macOS launchd agent: `scripts/com.prism.gateway.plist`
- `prism-desktop` package with dark chat UI
- Browser sync bridge: `prism/tools/browser_bridge.py`
- ACP client: `prism/acp/client.py`
- MCP HTTP/SSE transport: `prism/mcp/http_client.py`
- Gateway base module: `prism/gateway/base.py`
- `prism config set/get` CLI commands
- `prism browser open/close` CLI commands
- `prism gateway` CLI commands
- `prism skill` CLI commands
- `prism tools` CLI command
- `prism version` CLI command
- Smoke tests: `tests/test_full_smoke.py`
- MCP config loader tests: `tests/test_mcp_config_loader.py`
- Example config: `config.example.yaml`
- Browser echo service: `prism/tools/browser_echo.py`

### Changed
- README restructured for quick install and platform-specific guides
- INSTALL.md rewritten for Windows/macOS/Linux
- Providers package exports unified (`prism.providers`)

### Fixed
- Browser pytest event-loop compatibility
- Gateway import cycle (`prism/gateway/__init__.py`)
- Code executor timeout parameter
- Registry `CodeExecuteTool.execute` signature

### Notes
- Video tutorial and Feishu tutorial removed from repo per request
- Repo remains public; local tutorials kept in working tree only
- Test suite is currently green on core paths
