# Changelog

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
- `prism tools` CLI commands
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
