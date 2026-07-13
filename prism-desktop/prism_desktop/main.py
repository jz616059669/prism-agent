"""
PRISM Agent - 桌面客户端
基于 Flet 实现，比 Codex CLI 更现代
已连通真实 Agent 后端 + 浏览器控制 + 终端输出 + MCP 控制
"""

import sys
from pathlib import Path

# 让桌面端优先加载项目根 prism 包，避免被 venv site-packages 里的旧副本覆盖
REPO_ROOT = Path(__file__).resolve().parents[2]
DESKTOP_ROOT = Path(__file__).resolve().parent.parent
for _p in (str(REPO_ROOT), str(DESKTOP_ROOT), str(Path.cwd())):
    if _p not in sys.path:
        sys.path.insert(0, _p)

import os
import json
from datetime import datetime
import flet as ft
from typing import Optional
import markdown
import subprocess
import threading
from prism_desktop.i18n import gettext as _

from prism.logging import logger
import traceback

from prism.config import config as prism_config
from prism.agent import create_agent
from prism.tools.browser_bridge import open_page, page_snapshot, close_browser
INIT_ERROR_LOG = Path.home() / '.prism' / 'init-error.log'


from prism_desktop.sidebar import SidebarMixin
from prism_desktop.chat import ChatMixin
from prism_desktop.terminal import TerminalMixin
from prism_desktop.settings import SettingsMixin
from prism_desktop.system import SystemMixin
from prism_desktop.mcp import MCPMixin
from prism_desktop.browser import BrowserMixin


class PrismDesktop(SidebarMixin, ChatMixin, TerminalMixin, SettingsMixin, SystemMixin, MCPMixin, BrowserMixin):
    def __init__(self, page: ft.Page):
        self.page = page
        self.page.title = "PRISM Agent"
        self.page.theme_mode = ft.ThemeMode.DARK
        self.page.padding = 14
        self.page.window_width = 1320
        self.page.window_height = 800
        self.page.theme = ft.Theme(color_scheme_seed="blue", use_material3=True)
        self.page.on_keyboard_event = self._on_keyboard_event

        self._settings = {}
        
        self._status_icon = ft.Container(
            width=8, height=8,
            bgcolor=ft.Colors.GREEN_400,
            border_radius=4,
        )
        self.status_text = ft.Text(_("ready"), size=12, color=ft.Colors.ON_SURFACE, weight=ft.FontWeight.W_600)
        self.perf_text = ft.Text("", size=11, color=ft.Colors.ON_SURFACE_VARIANT, opacity=0.8, weight=ft.FontWeight.W_500)
        self._input_accent = None
        self.browser_status_icon = ft.Icon(ft.Icons.LANGUAGE_ROUNDED, size=18, color=ft.Colors.PRIMARY)
        self.browser_status_text = ft.Text(_("ready"), size=12, color=ft.Colors.ON_SURFACE, opacity=0.9, weight=ft.FontWeight.W_500)
        self.browser_connected = None
        self.messages = []
        self.browser_connected = False
        self._perf_fps = 0
        self._perf_frames = 0
        self._perf_last_ts = None
        self._perf_mem_mb = 0.0
        self._terminal_lines = ["PRISM Desktop 已启动"]
        self._init_error: Optional[BaseException] = None
        self.agent = None
        print("[BOOT] main.py loaded from:", __file__, flush=True)
        
        try:
            self._build_ui()
            self._bind_context_menu()
            self._bind_tray()
            self._maybe_show_setup_wizard()
            self._settings = self._load_settings()
            if hasattr(self.page, "run_task"):
                self._start_update_check()
            self._validate_and_create_agent()
        except Exception as exc:
            self.agent = None
            self._init_error = exc
            self._log_error("agent init fallback", exc)
            if hasattr(self, "retry_init_btn") and self.retry_init_btn:
                self.retry_init_btn.visible = True

        self.model_dropdown = ft.Dropdown(
            label="默认模型",
            options=[ft.dropdown.Option("step-3.7-flash")],
            value=prism_config.get("model.default", "step-3.7-flash") or "step-3.7-flash",
            width=260,
        )
        self.provider_textfield = ft.TextField(label=_("model_provider"), value=prism_config.get("model.provider", "stepfun") or "stepfun", width=260)
        self.base_url_textfield = ft.TextField(label=_("base_url"), value=prism_config.get("model.base_url", "https://api.stepfun.com/step_plan/v1") or "https://api.stepfun.com/step_plan/v1", width=260)
        self.api_key_textfield = ft.TextField(label=_("api_key"), password=True, can_reveal_password=True, value=prism_config.get("model.api_key", "") or "", width=260)
        self.review_enabled_switch = ft.Switch(label="后台复盘", value=bool(int(os.getenv("PRISM_REVIEW_ENABLED", "1") or 1)))
        self.review_interval_field = ft.TextField(label="", value=str(int(os.getenv("PRISM_REVIEW_INTERVAL", "5") or 5)), width=64, keyboard_type=ft.KeyboardType.NUMBER, dense=True, content_padding=ft.Padding(4, 2, 4, 2), text_size=12)
        self.review_enabled_switch.on_change = lambda e: (self._apply_review_env(), self._save_settings())
        self.review_interval_field.on_change = lambda e: (self._apply_review_env(), self._save_settings())

        self._save_settings_timer = None
        self._save_settings_delay = 0.5  # seconds

        try:
            self._build_ui()
            self._bind_context_menu()
            self._bind_tray()
            self._maybe_show_setup_wizard()
            self._settings = self._load_settings()
            if hasattr(self.page, "run_task"):
                self._start_update_check()
        except Exception as exc:
            import traceback
            tb = traceback.format_exc()
            try:
                INIT_ERROR_LOG.write_text(tb, encoding="utf-8")
            except Exception:
                logger.debug('desktop exception: %s', traceback.format_exc())
            print(f"[INIT ERROR] {exc}\n{tb}", flush=True)
            self._append_terminal(f"init error: {exc}")
            self._append_terminal(tb)
        # Update clock every second
        if hasattr(self.page, 'add_periodic_callback'):
            def _tick(_):
                self._update_clock()
            self.page.add_periodic_callback(_tick, 1000)
            self._start_perf_monitor()
            self.page.add_periodic_callback(lambda _: self._perf_tick(), 1000)
        presets = (self._settings.get("model_presets") or {})
        current_preset = self._settings.get("model_preset_name", "")
        if current_preset and current_preset in presets:
            p = presets[current_preset]
            if p.get("model"):
                if hasattr(self, "model_dropdown") and self.model_dropdown:
                    self.model_dropdown.value = p["model"]
            if p.get("provider"):
                if hasattr(self, "provider_textfield") and self.provider_textfield:
                    self.provider_textfield.value = p["provider"]
            if p.get("base_url"):
                if hasattr(self, "base_url_textfield") and self.base_url_textfield:
                    self.base_url_textfield.value = p["base_url"]
            if p.get("api_key"):
                if hasattr(self, "api_key_textfield") and self.api_key_textfield:
                    self.api_key_textfield.value = p["api_key"]
        self._apply_settings()
        try:
            self._init_mcp_servers()
        except Exception:
            logger.debug('desktop exception: %s', traceback.format_exc())
        try:
            from prism.mcp import mcp_client
            mcp_client.watch_config()
        except Exception:
            pass
        try:
            from prism.notification_system import notification_system
            notification_system.set_ui_callback(self._append_notification)
        except Exception:
            pass
        try:
            self._restore_runtime_state()
        except Exception:
            logger.debug('desktop exception: %s', traceback.format_exc())

    def _log_error(self, context: str, exc: BaseException) -> None:
        try:
            self._append_terminal(f"[ERROR] {context}: {exc}")
        except Exception:
            logger.debug('desktop exception: %s', traceback.format_exc())

    def _show_init_fallback(self, exc: BaseException) -> None:
        """初始化失败时仅输出到终端与日志，不展示 fallback UI。"""
        try:
            import traceback as tb_mod
            tb_text = tb_mod.format_exception(type(exc), exc, exc.__traceback__)
            tb_text = "".join(tb_text)
            try:
                INIT_ERROR_LOG.write_text(tb_text, encoding="utf-8")
            except Exception:
                logger.debug('desktop exception: %s', traceback.format_exc())
            self._append_terminal(f"[ERROR] agent init: {exc}")
            self._append_terminal(tb_text)
        except Exception:
            logger.debug('desktop exception: %s', traceback.format_exc())

    def _retry_init(self) -> None:
        """点击重试时重新初始化 Agent。"""
        try:
            self.page.clean()
        except Exception:
            logger.debug('desktop exception: %s', traceback.format_exc())
        try:
            self._build_ui()
            self._bind_context_menu()
            self._bind_tray()
            self._maybe_show_setup_wizard()
            self._settings = self._load_settings()
            if hasattr(self.page, "run_task"):
                self._start_update_check()
            self._set_status("已重试", ft.Colors.GREEN_400)
            if hasattr(self, "retry_init_btn") and self.retry_init_btn:
                self.retry_init_btn.visible = False
            self.page.update()
        except Exception as exc:
            self._log_error("agent init retry", exc)
            self._show_init_fallback(exc)

    def _structured_log(self, level: str, event: str, **fields) -> None:
        try:
            line = {"ts": datetime.now().isoformat(timespec="seconds"), "level": level, "event": event, **fields}
            self._append_terminal(f"[{line['level']}] {line['event']} | {fields}")
        except Exception:
            logger.debug('desktop exception: %s', traceback.format_exc())

    def _log_to_file(self, level: str, event: str, **fields) -> None:
        try:
            safe_fields = {k: (str(v) if not isinstance(v, (str, int, float, bool, type(None))) else v) for k, v in fields.items()}
            entry = {"ts": datetime.now().isoformat(timespec="seconds"), "level": level, "event": event, **safe_fields}
            log_path = Path.home() / ".prism" / "prism-desktop.log"
            log_path.parent.mkdir(parents=True, exist_ok=True)
            with open(log_path, "a", encoding="utf-8") as f:
                f.write(json.dumps(entry, ensure_ascii=False) + "\n")
        except Exception:
            logger.debug('desktop exception: %s', traceback.format_exc())

    def _on_keyboard_event(self, e: ft.KeyboardEvent):
        try:
            if e.ctrl and e.key == "Enter":
                if hasattr(self, "input_field") and self.input_field and not self.input_field.disabled:
                    self._send()
            elif e.ctrl and e.key == ",":
                if hasattr(self, "settings_panel"):
                    self._apply_settings()
            elif e.ctrl and e.key == "n":
                if hasattr(self, "_new_chat"):
                    self._new_chat()
        except Exception as exc:
            self._log_error("keyboard handler", exc)

    def _start_update_check(self):
        if os.environ.get("PRISM_SKIP_UPDATE_CHECK", "").strip() in ("1", "true", "yes", "y"):
            return
        if hasattr(self.page, "run_task"):
            self.page.run_task(self._check_for_updates)

    async def _check_for_updates(self):
        try:
            import urllib.request, json
            req = urllib.request.Request(
                "https://api.github.com/repos/jz616059669/prism-agent/releases/latest",
                headers={"User-Agent": "PRISM-Desktop"},
            )
            with urllib.request.urlopen(req, timeout=8) as resp:
                data = json.loads(resp.read().decode("utf-8"))
            latest = data.get("tag_name", "").lstrip("v")
            current = prism_config.get("app.version", "0.0.0")
            if latest and latest != current:
                self._set_status(f"发现新版本 {latest}", ft.Colors.AMBER_400)
                self._append_terminal(f"update available: {latest} (current {current})")
        except Exception:
            # 静默跳过，避免刷屏
            return

    def _validate_config(self) -> bool:
        try:
            provider = (getattr(self, "provider_textfield", None) or type("T", (), {"value": ""})()).value or ""
            base_url = (getattr(self, "base_url_textfield", None) or type("T", (), {"value": ""})()).value or ""
            api_key = (getattr(self, "api_key_textfield", None) or type("T", (), {"value": ""})()).value or ""
            model = (getattr(self, "model_dropdown", None) or type("T", (), {"value": ""})()).value or ""
            missing = []
            if not provider:
                missing.append("模型提供商")
            if not base_url:
                missing.append("Base URL")
            if not api_key:
                missing.append("API Key")
            if not model:
                missing.append("默认模型")
            if missing:
                try:
                    self._set_status(f"配置缺失：{', '.join(missing)}", ft.Colors.RED_400)
                except Exception:
                    logger.debug('desktop exception: %s', traceback.format_exc())
                return False
            return True
        except Exception:
            logger.debug('desktop exception: %s', traceback.format_exc())
            return False

    def _validate_and_create_agent(self) -> bool:
        self.agent = None
        if not self._validate_config():
            raise RuntimeError("configuration validation failed")
        try:
            self.agent = create_agent(enable_auto_memory=True)
            return True
        except Exception as exc:
            self.agent = None
            self._log_error("agent init", exc)
            raise

    def _maybe_show_setup_wizard(self):
        try:
            has_key = bool(prism_config.get("model.api_key"))
            has_provider = bool(prism_config.get("model.provider"))
            mcp_configured = bool(prism_config.get("mcp.servers"))
            if has_key and has_provider:
                if mcp_configured:
                    return
        except Exception as exc:
            self._log_error("setup wizard check", exc)
        wizard_provider = ft.TextField(label=_("model_provider"), value="stepfun", width=320)
        wizard_key = ft.TextField(label=_("api_key"), password=True, can_reveal_password=True, width=320)
        wizard_model = ft.TextField(label=_("default_model"), value="step-3.7-flash", width=320)

        def _save(_):
            try:
                if wizard_provider.value.strip():
                    prism_config.set("model.provider", wizard_provider.value.strip())
                if wizard_key.value.strip():
                    prism_config.set("model.api_key", wizard_key.value.strip())
                if wizard_model.value.strip():
                    prism_config.set("model.default", wizard_model.value.strip())
                self._init_mcp_servers()
                self.page.close_dialog()
                self._append_terminal("setup wizard saved")
                self._set_status("配置已保存", ft.Colors.GREEN_400)
            except Exception as exc:
                self._log_error("setup wizard save", exc)
                self._set_status(f"保存失败：{exc}", ft.Colors.RED_400)

        self.page.dialog = ft.AlertDialog(
            title=ft.Text("首次运行配置向导", size=16, weight=ft.FontWeight.BOLD),
            content=ft.Column(
                [
                    ft.Text("请先填写模型配置，否则无法正常对话。", size=13, color=ft.Colors.ON_SURFACE_VARIANT),
                    ft.Container(height=14),
                    wizard_provider,
                    ft.Container(height=6),
                    wizard_key,
                    ft.Container(height=6),
                    wizard_model,
                ],
                tight=True,
                spacing=0,
            ),
            actions=[ft.TextButton("保存", on_click=_save, style=ft.ButtonStyle(bgcolor=ft.Colors.PRIMARY, color=ft.Colors.ON_PRIMARY, shape=ft.RoundedRectangleBorder(radius=12)))],
        )
        self.page.dialog.open = True
        self.page.update()

    def _init_mcp_servers(self) -> None:
        try:
            from prism.mcp.config_loader import setup_mcp_servers
            client = setup_mcp_servers()
            self._append_terminal(f"mcp servers loaded: {len(client.servers)}")
            self._append_mcp(f"已加载 MCP 服务器：{len(client.servers)}")
            self._refresh_mcp()
        except Exception as exc:
            self._log_error("init mcp servers", exc)

    def _refresh_mcp(self) -> None:
        if not hasattr(self, "mcp_server_list") or self.mcp_server_list is None:
            return
        try:
            from prism.mcp import mcp_client
            servers = getattr(mcp_client, "servers", {})
            tools_map = getattr(mcp_client, "tools", {})
            self.mcp_server_list.controls.clear()
            self.mcp_status_list.controls.clear()
            self._mcp_tool_counts = {}
            if not servers:
                self.mcp_server_list.controls.append(ft.Text("未配置 MCP 服务器", size=11, color=ft.Colors.ON_SURFACE_VARIANT))
            else:
                for name, srv in servers.items():
                    status = getattr(srv, "status", "unknown")
                    icon = ft.Icons.CHECK_CIRCLE_ROUNDED if status == "connected" else ft.Icons.ERROR_ROUNDED
                    color = ft.Colors.GREEN_400 if status == "connected" else ft.Colors.RED_400
                    row = ft.Row([
                        ft.Icon(icon, size=14, color=color),
                        ft.Text(f"{name}", size=11, color=ft.Colors.ON_SURFACE, expand=True),
                        ft.Text(status, size=10, color=ft.Colors.ON_SURFACE_VARIANT),
                    ], spacing=6, tight=True)
                    self.mcp_server_list.controls.append(row)
                    try:
                        tool_names = [t.get("name") for t in tools_map.get(name, {}).get("tools", []) if isinstance(t, dict)]
                        self._mcp_tool_counts[name] = len(tool_names)
                    except Exception:
                        self._mcp_tool_counts[name] = 0
                    status_row = ft.Row([
                        ft.Text("工具数", size=10, color=ft.Colors.ON_SURFACE_VARIANT),
                        ft.Text(str(self._mcp_tool_counts.get(name, 0)), size=10, color=ft.Colors.ON_SURFACE),
                    ], spacing=6, tight=True)
                    self.mcp_status_list.controls.append(status_row)
            self.mcp_server_list.update()
            self.mcp_status_list.update()
            self._append_terminal(f"mcp refreshed: {len(servers)} servers")
        except Exception as exc:
            self._log_error("refresh mcp", exc)

    def _save_settings_debounced(self) -> None:
        if self._save_settings_timer is not None:
            self._save_settings_timer.cancel()
        self._save_settings_timer = threading.Timer(self._save_settings_delay, self._save_settings)
        self._save_settings_timer.start()

    def _bind_context_menu(self) -> None:
        self.page.on_resized = lambda e: self._save_settings_debounced()
        try:
            self.page.window_prevent_close = True
            self.page.on_window_event = lambda e: (
                self._persist_runtime_state(),
                getattr(self.page, "window_close", lambda: None)(),
            )
        except Exception:
            try:
                self._persist_runtime_state()
            except Exception:
                pass

    def _bind_tray(self) -> None:
        try:
            if sys.platform == "darwin":
                self._append_terminal("macOS detected: tray disabled")
                self._tray_icon = None
                return
            try:
                import threading
                import pystray
                from PIL import Image, ImageDraw

                def _create_tray_image() -> Image.Image:
                    img = Image.new("RGB", (64, 64), (0, 0, 0))
                    d = ImageDraw.Draw(img)
                    d.text((16, 16), "P", fill=(255, 255, 255))
                    return img

                def _on_tray_click(icon, item):
                    try:
                        if hasattr(self, "page") and self.page is not None:
                            def _ui_show():
                                try:
                                    if hasattr(self.page, "window_show"):
                                        self.page.window_show()
                                    else:
                                        self.page.visible = True
                                    if hasattr(self, "input_field") and self.input_field is not None:
                                        try:
                                            self.input_field.focus()
                                        except Exception as exc:
                                            logger.debug("input focus failed: %s", exc)
                                    if hasattr(self, "_refresh_sessions"):
                                        try:
                                            self._refresh_sessions()
                                        except Exception as exc:
                                            logger.debug("refresh sessions failed: %s", exc)
                                    if hasattr(self, "_refresh_mcp"):
                                        try:
                                            self._refresh_mcp()
                                        except Exception as exc:
                                            logger.debug("refresh mcp failed: %s", exc)
                                    if hasattr(self, "_refresh_skills"):
                                        try:
                                            self._refresh_skills()
                                        except Exception as exc:
                                            logger.debug("refresh skills failed: %s", exc)
                                    try:
                                        self._set_status("就绪", ft.Colors.GREEN_400)
                                    except Exception as exc:
                                        logger.debug("set status ready failed: %s", exc)
                                    try:
                                        self.page.update()
                                    except Exception as exc:
                                        logger.debug("page update failed: %s", exc)
                                except Exception:
                                    logger.debug('desktop exception: %s', traceback.format_exc())
                            try:
                                self.page.run_task(_ui_show)
                            except Exception:
                                _ui_show()
                    except Exception:
                        logger.debug('desktop exception: %s', traceback.format_exc())

                def _on_exit(icon, item):
                    icon.stop()
                    try:
                        if hasattr(self, "page") and self.page is not None:
                            try:
                                self.page.window_close()
                            except Exception:
                                pass
                    except Exception:
                        logger.debug('desktop exception: %s', traceback.format_exc())

                menu = pystray.Menu(
                    pystray.MenuItem(_("open_main"), _on_tray_click),
                    pystray.MenuItem(_("exit_app"), _on_exit),
                )
                icon = pystray.Icon("PRISM", _create_tray_image(), "PRISM Agent", menu)
                t = threading.Thread(target=icon.run, daemon=True)
                t.start()
                self._tray_icon = icon
            except Exception as exc:
                self._log_error("tray icon create", exc)
                self._tray_icon = None
        except Exception as exc:
            self._log_error("tray bind outer", exc)

    def _apply_theme(self, name: str):
        name = (name or "Dark").strip()
        if name == "Light":
            self.page.theme_mode = ft.ThemeMode.LIGHT
            self.page.theme = ft.Theme(color_scheme_seed="blue", use_material3=True)
        elif name == "Midnight":
            self.page.theme_mode = ft.ThemeMode.DARK
            self.page.theme = ft.Theme(color_scheme_seed="indigo")
        elif name == "Warm":
            self.page.theme_mode = ft.ThemeMode.LIGHT
            self.page.theme = ft.Theme(color_scheme_seed="orange")
        else:
            self.page.theme_mode = ft.ThemeMode.DARK
            self.page.theme = ft.Theme(color_scheme_seed="blue", use_material3=True)
        self.page.animate = ft.Animation(duration=300, curve=ft.AnimationCurve.EASE_IN_OUT)
        self.page.update()
        self._append_terminal(f"theme -> {name}")
        self._save_settings()


    def _build_appbar(self) -> ft.AppBar:
        self.title_text = ft.Text("PRISM Agent", size=20, weight=ft.FontWeight.BOLD, color=ft.Colors.ON_SURFACE)
        self.theme_icon_btn = ft.IconButton(icon=ft.Icons.SETTINGS_ROUNDED, tooltip="切换主题", icon_color=ft.Colors.ON_SURFACE_VARIANT, bgcolor=ft.Colors.with_opacity(0, ft.Colors.TRANSPARENT), style=ft.ButtonStyle(shape=ft.CircleBorder(), overlay_color=ft.Colors.with_opacity(0.15, ft.Colors.ON_SURFACE_VARIANT)))
        self.theme_icon_btn.on_click = lambda e: self._cycle_theme()
        self.minimize_btn = ft.IconButton(icon=ft.Icons.MINIMIZE_ROUNDED, tooltip=_("minimize_to_tray"), icon_color=ft.Colors.ON_SURFACE_VARIANT, bgcolor=ft.Colors.with_opacity(0, ft.Colors.TRANSPARENT), style=ft.ButtonStyle(shape=ft.CircleBorder(), overlay_color=ft.Colors.with_opacity(0.15, ft.Colors.ON_SURFACE_VARIANT)))
        self.minimize_btn.on_click = lambda e: self._minimize_to_tray()
        self.about_btn = ft.IconButton(icon=ft.Icons.INFO, tooltip=_("about"), icon_color=ft.Colors.ON_SURFACE_VARIANT, bgcolor=ft.Colors.with_opacity(0, ft.Colors.TRANSPARENT), style=ft.ButtonStyle(shape=ft.CircleBorder(), overlay_color=ft.Colors.with_opacity(0.15, ft.Colors.ON_SURFACE_VARIANT)))
        self.about_btn.on_click = lambda e: self._about(e)
        self.sidebar_toggle_btn = ft.IconButton(icon=ft.Icons.MENU_ROUNDED, tooltip="折叠侧边栏", icon_color=ft.Colors.ON_SURFACE_VARIANT, bgcolor=ft.Colors.with_opacity(0, ft.Colors.TRANSPARENT), style=ft.ButtonStyle(shape=ft.CircleBorder(), overlay_color=ft.Colors.with_opacity(0.15, ft.Colors.ON_SURFACE_VARIANT)))
        self.sidebar_toggle_btn.on_click = lambda e: self._toggle_sidebar()
        # Quick action buttons in appbar
        quick_actions = ft.Row(
            [
                ft.IconButton(
                    icon=ft.Icons.CLEAR_ALL_ROUNDED,
                    tooltip="清空对话",
                    icon_color=ft.Colors.ON_SURFACE_VARIANT,
                    bgcolor=ft.Colors.with_opacity(0, ft.Colors.TRANSPARENT),
                    style=ft.ButtonStyle(shape=ft.CircleBorder(), overlay_color=ft.Colors.with_opacity(0.12, ft.Colors.ON_SURFACE)),
                    on_click=lambda e: self._clear_chat(),
                ),
                ft.IconButton(
                    icon=ft.Icons.BOOKMARK_ROUNDED,
                    tooltip="保存会话",
                    icon_color=ft.Colors.ON_SURFACE_VARIANT,
                    bgcolor=ft.Colors.with_opacity(0, ft.Colors.TRANSPARENT),
                    style=ft.ButtonStyle(shape=ft.CircleBorder(), overlay_color=ft.Colors.with_opacity(0.12, ft.Colors.ON_SURFACE)),
                    on_click=lambda e: self._save_session(),
                ),
            ],
            spacing=2,
        )

        return ft.AppBar(
            title=self.title_text,
            actions=[
                self.sidebar_toggle_btn,
                self.theme_icon_btn,
                self.minimize_btn,
                quick_actions,
                self.about_btn,
            ],
            elevation=6,
            bgcolor=ft.Colors.SURFACE,
        )

    def _toggle_sidebar(self):
        if not hasattr(self, "_sidebar_container"):
            return
        was_visible = self._sidebar_container.visible
        self._sidebar_container.visible = not was_visible
        self._sidebar_container.width = 0 if was_visible else 300
        self._sidebar_container.animate = ft.Animation(duration=300, curve=ft.AnimationCurve.EASE_IN_OUT)
        self._sidebar_container.update()
        self._settings["sidebar_collapsed"] = str(not was_visible).lower()
        self._save_settings()
        self.page.update()

    def _animate_sidebar_cards(self):
        try:
            def _run():
                try:
                    time.sleep(0.1)
                    for card in self._sidebar_container.content.controls:
                        if hasattr(card, 'animate_opacity'):
                            card.opacity = 1
                            card.update()
                            time.sleep(0.05)
                except Exception:
                    logger.debug('desktop exception: %s', traceback.format_exc())
            try:
                self.page.run_task(_run)
            except Exception:
                _run()
        except Exception:
            logger.debug('desktop exception: %s', traceback.format_exc())

    def _cycle_theme(self):
        current = self._settings.get("theme", "Dark")
        themes = ["Dark", "Light", "Midnight", "Warm"]
        idx = themes.index(current) if current in themes else 0
        next_theme = themes[(idx + 1) % len(themes)]
        self._settings["theme"] = next_theme
        if hasattr(self, "theme_dropdown") and self.theme_dropdown is not None:
            self.theme_dropdown.value = next_theme
        self._apply_theme(next_theme)

    def _minimize_to_tray(self):
        try:
            if hasattr(self.page, "window_hide"):
                self.page.window_hide()
            else:
                self.page.visible = False
            self._append_terminal("minimized to tray")
        except Exception:
            logger.debug('desktop exception: %s', traceback.format_exc())

    def _build_ui(self):
        self._clock_text = ft.Text(datetime.now().strftime("%H:%M:%S"), size=11, color=ft.Colors.ON_SURFACE_VARIANT, weight=ft.FontWeight.W_500, opacity=0.95)
        self.page.appbar = self._build_appbar()
        self._chat_container = ft.Container(self._build_chat(), expand=True, padding=ft.Padding(0, 4, 0, 4))
        sidebar = self._build_sidebar()
        self._right_container = ft.Container(self._build_right_panel(), width=320, border=ft.Border(left=ft.border.BorderSide(1, ft.Colors.OUTLINE_VARIANT)))
        if str(self._settings.get("sidebar_collapsed", "false")).lower() == "true":
            sidebar.visible = False
            sidebar.width = 0
            sidebar.padding = 0
        if isinstance(self._settings.get("sidebar_width"), int):
            sidebar.width = int(self._settings.get("sidebar_width"))
        if isinstance(self._settings.get("chat_width"), int):
            self._chat_container.width = int(self._settings.get("chat_width"))
        if isinstance(self._settings.get("right_width"), int):
            self._right_container.width = int(self._settings.get("right_width"))
        else:
            self._right_container.width = int(self._settings.get("sidebar_width", 320))
        self.page.add(
            ft.Row(
                [
                    sidebar,
                    ft.VerticalDivider(width=1, color=ft.Colors.OUTLINE_VARIANT, opacity=0.4),
                    self._chat_container,
                    ft.VerticalDivider(width=1, color=ft.Colors.OUTLINE_VARIANT, opacity=0.4),
                    self._right_container,
                ],
                expand=True,
                spacing=0,
            )
        )
    
    def _open_preset_manager(self):
        presets = (self._settings.get("model_presets") or {})
        preset_names = list(presets.keys())
        current_preset = self._settings.get("model_preset_name", "")

        def on_dismiss(e):
            pass

        def save_as_preset(e):
            name = preset_name_field.value.strip()
            if not name:
                return
            presets[name] = {
                "model": self.model_dropdown.value,
                "provider": self.provider_textfield.value,
                "base_url": (self.base_url_textfield.value or "").strip(),
                "api_key": self.api_key_textfield.value,
            }
            self._settings["model_presets"] = presets
            self._settings["model_preset_name"] = name
            self._save_settings()
            preset_dlg.open = False
            self.page.update()
            self._refresh_preset_dropdown()
            self._set_status(f"预设已保存：{name}")

        preset_name_field = ft.TextField(hint_text="新预设名称", width=280, border_radius=14)

        preset_buttons = []
        for name in preset_names:
            is_active = name == current_preset

            def apply_preset(e, n=name):
                p = presets.get(n, {})
                if p.get("model"):
                    self.model_dropdown.value = p["model"]
                if p.get("provider"):
                    self.provider_textfield.value = p["provider"]
                if p.get("base_url"):
                    self.base_url_textfield.value = p["base_url"]
                if p.get("api_key"):
                    self.api_key_textfield.value = p["api_key"]
                self._settings["model_preset_name"] = n
                self._save_settings()
                self._set_status(f"已切换预设：{n}")
                preset_dlg.open = False
                self.page.update()

            def delete_preset(e, n=name):
                if n in presets:
                    del presets[n]
                    self._settings["model_presets"] = presets
                    if current_preset == n:
                        self._settings.pop("model_preset_name", None)
                    self._save_settings()
                    preset_dlg.open = False
                    self.page.update()
                    self._refresh_preset_dropdown()
                    self._set_status(f"预设已删除：{n}")

            preset_buttons.append(
                ft.Row([
                    ft.Text(n, expand=True, color=ft.Colors.PRIMARY if is_active else ft.Colors.ON_SURFACE),
                    ft.IconButton(ft.Icons.CHECK_CIRCLE_ROUNDED if is_active else ft.Icons.RADIO_BUTTON_UNCHECKED_ROUNDED, tooltip="应用", icon_color=ft.Colors.PRIMARY if is_active else ft.Colors.ON_SURFACE_VARIANT, on_click=apply_preset),
                    ft.IconButton(ft.Icons.DELETE_ROUNDED, tooltip="删除", icon_color=ft.Colors.ERROR, on_click=delete_preset),
                ], spacing=6, tight=True)
            )

        preset_dlg = ft.AlertDialog(
            modal=True,
            title=ft.Text("预设管理", size=16, weight=ft.FontWeight.BOLD, color=ft.Colors.ON_SURFACE),
            bgcolor=ft.Colors.SURFACE,
            content=ft.Column([
                ft.Text("保存当前配置为新预设：", size=12, color=ft.Colors.ON_SURFACE_VARIANT),
                ft.Row([preset_name_field, ft.IconButton(ft.Icons.ADD_ROUNDED, tooltip="保存", icon_color=ft.Colors.PRIMARY, on_click=save_as_preset)], spacing=8, tight=True),
                ft.Container(height=14),
                ft.Text("已有预设：", size=12, color=ft.Colors.ON_SURFACE_VARIANT),
                ft.Column(preset_buttons, spacing=6, tight=True, scroll=ft.ScrollMode.AUTO),
            ], tight=True, spacing=6, height=400, width=320),
            actions=[ft.TextButton("关闭", on_click=lambda e: setattr(preset_dlg, 'open', False) or self.page.update())],
            actions_alignment=ft.MainAxisAlignment.END,
        )
        self.page.dialog = preset_dlg
        preset_dlg.open = True
        self.page.update()

    def _refresh_preset_dropdown(self):
        presets = (self._settings.get("model_presets") or {})
        preset_names = list(presets.keys())
        current = self._settings.get("model_preset_name", "")
        if hasattr(self, "model_dropdown"):
            self.model_dropdown.options = [ft.dropdown.Option(n) for n in preset_names] if preset_names else []
            if current and current in preset_names:
                self.model_dropdown.value = current
            elif preset_names:
                self.model_dropdown.value = preset_names[0]
            else:
                self.model_dropdown.value = ""
            self.model_dropdown.update()

    def _save_preset(self):
        name = self.model_dropdown.value
        if not name:
            self._set_status("请先选择或输入预设名称", ft.Colors.RED_400)
            return
        presets = (self._settings.get("model_presets") or {})
        presets[name] = {
            "model": self.model_dropdown.value,
            "provider": self.provider_textfield.value,
            "base_url": (self.base_url_textfield.value or "").strip(),
            "api_key": self.api_key_textfield.value,
        }
        self._settings["model_presets"] = presets
        self._settings["model_preset_name"] = name
        self._save_settings()
        self._set_status(f"预设已保存：{name}")

    def _build_sidebar(self) -> ft.Container:
        self._sidebar_container = ft.Container(animate=ft.Animation(duration=300, curve=ft.AnimationCurve.EASE_IN_OUT),
            content=ft.Column(
                [
                    ft.Text("PRISM", size=22, weight=ft.FontWeight.BOLD, color=ft.Colors.ON_SURFACE),
                    ft.Container(height=6),
                    ft.Text("v2.1.5", size=12, color=ft.Colors.ON_SURFACE_VARIANT, opacity=0.85),
                ],
                tight=True,
                spacing=6,
                scroll=ft.ScrollMode.AUTO,
            ),
            width=300,
            padding=18,
            gradient=ft.LinearGradient(
                colors=[ft.Colors.SURFACE, ft.Colors.SURFACE_CONTAINER],
                begin=ft.Alignment(0, -1),
                end=ft.Alignment(0, 1),
            ),
            bgcolor=ft.Colors.SURFACE,
            border_radius=34,
        )

        save_btn = ft.Button(_("save_settings"), icon=ft.Icons.SAVE_ROUNDED, width=260, style=ft.ButtonStyle(shape=ft.RoundedRectangleBorder(radius=12), padding=ft.Padding(18, 14, 18, 14), bgcolor=ft.Colors.PRIMARY_CONTAINER, color=ft.Colors.ON_PRIMARY_CONTAINER), animate_scale=ft.Animation(duration=180, curve=ft.AnimationCurve.EASE_IN_OUT))
        save_btn.on_click = lambda e: self._save_config()

        browser_deps = self._check_browser_dependencies()
        self._browser_deps_ok = browser_deps.get("playwright") and browser_deps.get("chromium")
        browser_hint = ft.Text(
            "本机未安装 playwright / Chromium，浏览器控制不可用" if not self._browser_deps_ok else "浏览器控制已就绪",
            size=11,
            color=ft.Colors.ON_SURFACE_VARIANT if self._browser_deps_ok else ft.Colors.ERROR,
            opacity=0.9,
        )
        self.url_field = ft.TextField(hint_text="输入网址...", width=260, border_radius=12)
        browser_open_btn = ft.Button("打开网页", icon=ft.Icons.LANGUAGE_ROUNDED, width=260, style=ft.ButtonStyle(shape=ft.RoundedRectangleBorder(radius=12), padding=ft.Padding(18, 14, 18, 14), bgcolor=ft.Colors.SURFACE_CONTAINER,
                     color=ft.Colors.ON_SURFACE), animate_scale=ft.Animation(duration=180, curve=ft.AnimationCurve.EASE_IN_OUT), disabled=not self._browser_deps_ok)
        browser_open_btn.on_click = lambda e: self._browser_open()
        browser_snapshot_btn = ft.Button("读取页面快照", icon=ft.Icons.ARTICLE_ROUNDED, width=260, style=ft.ButtonStyle(shape=ft.RoundedRectangleBorder(radius=12), padding=ft.Padding(18, 14, 18, 14), bgcolor=ft.Colors.SURFACE_CONTAINER,
                     color=ft.Colors.ON_SURFACE), animate_scale=ft.Animation(duration=180, curve=ft.AnimationCurve.EASE_IN_OUT), disabled=not self._browser_deps_ok)
        browser_snapshot_btn.on_click = lambda e: self._browser_snapshot()
        browser_close_btn = ft.Button(_("close_browser"), icon=ft.Icons.CLOSE_ROUNDED, width=260, style=ft.ButtonStyle(shape=ft.RoundedRectangleBorder(radius=12), padding=ft.Padding(18, 14, 18, 14), bgcolor=ft.Colors.ERROR_CONTAINER, color=ft.Colors.ON_ERROR_CONTAINER), animate_scale=ft.Animation(duration=180, curve=ft.AnimationCurve.EASE_IN_OUT), disabled=not self._browser_deps_ok)
        browser_close_btn.on_click = lambda e: self._browser_close()

        # MCP
        self.mcp_refresh_btn = ft.Button(_("refresh_mcp"), icon=ft.Icons.REFRESH_ROUNDED, width=260, style=ft.ButtonStyle(shape=ft.RoundedRectangleBorder(radius=12), padding=ft.Padding(18, 14, 18, 14), bgcolor=ft.Colors.SURFACE_CONTAINER,
                     color=ft.Colors.ON_SURFACE), animate_scale=ft.Animation(duration=180, curve=ft.AnimationCurve.EASE_IN_OUT))
        self.mcp_refresh_btn.on_click = lambda e: self._refresh_mcp()
        self.mcp_server_list = ft.Column(spacing=4, tight=True)
        self.mcp_status_list = ft.Column(spacing=3, tight=True)
        self._mcp_tool_counts: Dict[str, int] = {}

        # Skills
        self.skill_refresh_btn = ft.Button(_("refresh_skills"), icon=ft.Icons.REFRESH_ROUNDED, width=260, style=ft.ButtonStyle(shape=ft.RoundedRectangleBorder(radius=12), padding=ft.Padding(18, 14, 18, 14), bgcolor=ft.Colors.SURFACE_CONTAINER,
                     color=ft.Colors.ON_SURFACE), animate_scale=ft.Animation(duration=180, curve=ft.AnimationCurve.EASE_IN_OUT))
        self.skill_refresh_btn.on_click = lambda e: self._refresh_skills()
        self.skill_search = ft.TextField(hint_text=_("skill_search_placeholder"), width=240, border_radius=12, dense=True, border=ft.Border.all(1, ft.Colors.OUTLINE_VARIANT), content_padding=ft.Padding(8, 6, 8, 6), bgcolor=ft.Colors.SURFACE_CONTAINER, on_change=lambda e: self._filter_skills(e.control.value or ""))
        self.skill_install_field = ft.TextField(hint_text=_("install_skill_placeholder"), width=260, border_radius=12)
        self.skill_install_btn = ft.Button(_("install_skill"), icon=ft.Icons.DOWNLOAD_ROUNDED, width=260, style=ft.ButtonStyle(shape=ft.RoundedRectangleBorder(radius=12), padding=ft.Padding(18, 14, 18, 14), bgcolor=ft.Colors.SURFACE_CONTAINER,
                     color=ft.Colors.ON_SURFACE), animate_scale=ft.Animation(duration=180, curve=ft.AnimationCurve.EASE_IN_OUT))
        self.skill_install_btn.on_click = lambda e: self._install_skill_from_ui()
        self.skill_list = ft.Column(spacing=4, tight=True)
        self._skill_all_items: List[dict] = []
        self.hub_search = ft.TextField(hint_text=_("skill_hub_search"), width=200, border_radius=16, dense=True, border=ft.Border.all(1, ft.Colors.OUTLINE_VARIANT), content_padding=ft.Padding(8, 6, 8, 6), bgcolor=ft.Colors.SURFACE_CONTAINER)
        self.hub_browse_btn = ft.Button(_("skill_hub_browse"), icon=ft.Icons.PUBLIC_ROUNDED, width=100, style=ft.ButtonStyle(shape=ft.RoundedRectangleBorder(radius=10), padding=ft.Padding(10, 8, 10, 8), bgcolor=ft.Colors.SURFACE_CONTAINER, color=ft.Colors.ON_SURFACE), animate_scale=ft.Animation(duration=180, curve=ft.AnimationCurve.EASE_IN_OUT))
        self.hub_browse_btn.on_click = lambda e: self._browse_hub_skills()
        self.hub_list = ft.Column(spacing=4, tight=True)
        self._hub_all_items: List[dict] = []

        # Workflow
        self.workflow_refresh_btn = ft.Button("刷新工作流", icon=ft.Icons.REFRESH_ROUNDED, width=260, style=ft.ButtonStyle(shape=ft.RoundedRectangleBorder(radius=12), padding=ft.Padding(18, 14, 18, 14), bgcolor=ft.Colors.SURFACE_CONTAINER,
                     color=ft.Colors.ON_SURFACE), animate_scale=ft.Animation(duration=180, curve=ft.AnimationCurve.EASE_IN_OUT))
        self.workflow_refresh_btn.on_click = lambda e: self._refresh_workflows()
        self.workflow_list = ft.Column(spacing=4, tight=True)
        self._workflow_items: List[dict] = []
        self.usage_calls_text = ft.Text("0", size=14, weight=ft.FontWeight.BOLD, color=ft.Colors.ON_SURFACE)
        self.usage_success_text = ft.Text("0%", size=14, weight=ft.FontWeight.BOLD, color=ft.Colors.ON_SURFACE)
        self.usage_latency_text = ft.Text("0ms", size=14, weight=ft.FontWeight.BOLD, color=ft.Colors.ON_SURFACE)
        self.usage_tokens_text = ft.Text("0", size=14, weight=ft.FontWeight.BOLD, color=ft.Colors.ON_SURFACE)
        self.usage_cost_text = ft.Text("$0", size=14, weight=ft.FontWeight.BOLD, color=ft.Colors.ON_SURFACE)
        self.persona_dropdown = ft.Dropdown(
            options=[],
            label="选择角色",
            width=260,
            border_radius=16,
            bgcolor=ft.Colors.SURFACE_CONTAINER,
            value="default",
            on_change=lambda e: self._apply_persona(e.control.value),
        )

        # 会话
        self.session_new_btn = ft.IconButton(icon=ft.Icons.ADD_ROUNDED, tooltip="新建对话", icon_color=ft.Colors.PRIMARY, bgcolor=ft.Colors.with_opacity(0.08, ft.Colors.PRIMARY), style=ft.ButtonStyle(shape=ft.CircleBorder(), overlay_color=ft.Colors.with_opacity(0.15, ft.Colors.PRIMARY)))
        self.session_new_btn.on_click = lambda e: self._new_session()
        self.session_name_field = ft.TextField(hint_text="会话名称", width=180, border_radius=12)
        self.session_save_btn = ft.Button("保存会话", icon=ft.Icons.BOOKMARK_ROUNDED, width=100, style=ft.ButtonStyle(shape=ft.RoundedRectangleBorder(radius=10), padding=ft.Padding(10, 8, 10, 8), bgcolor=ft.Colors.PRIMARY_CONTAINER, color=ft.Colors.ON_PRIMARY_CONTAINER), animate_scale=ft.Animation(duration=180, curve=ft.AnimationCurve.EASE_IN_OUT))
        self.session_save_btn.on_click = lambda e: self._save_session()
        self.session_search = ft.TextField(
            hint_text="搜索会话...",
            dense=True,
            border_radius=16,
            height=32,
            content_padding=ft.Padding(8, 6, 8, 6),
            on_change=lambda e: self._filter_sessions(e.control.value or ""),
        )
        self.session_list = ft.Column(spacing=6, tight=True, scroll=ft.ScrollMode.AUTO)
        self._session_empty_state = ft.Container(
            content=ft.Column(
                [
                    ft.Icon(ft.Icons.CHAT_BUBBLE_OUTLINE_ROUNDED, size=28, color=ft.Colors.ON_SURFACE_VARIANT, opacity=0.5),
                    ft.Container(height=6),
                    ft.Text("暂无保存的会话", size=12, color=ft.Colors.ON_SURFACE_VARIANT, opacity=0.95),
                ],
                alignment=ft.MainAxisAlignment.CENTER,
                horizontal_alignment=ft.CrossAxisAlignment.CENTER,
                tight=True,
            ),
            padding=ft.Padding(48, 48, 48, 48),
            border_radius=12,
            bgcolor=ft.Colors.with_opacity(0.6, ft.Colors.SURFACE_CONTAINER),
        )

        sidebar_content = self._sidebar_container.content
        sidebar_content.controls.extend([
            ft.Container(
                content=ft.Column([
                    ft.Row([ft.Text("模型配置", size=12, weight=ft.FontWeight.BOLD, color=ft.Colors.ON_SURFACE), ft.Icon(ft.Icons.TUNE_ROUNDED, size=14, color=ft.Colors.PRIMARY)], spacing=6, tight=True),
                    ft.Container(height=24),
                    # Preset selector
                    ft.Row([
                        self.model_dropdown,
                        ft.IconButton(icon=ft.Icons.BOOKMARK_ROUNDED, tooltip="保存为预设", icon_color=ft.Colors.ON_SURFACE_VARIANT, bgcolor=ft.Colors.with_opacity(0, ft.Colors.TRANSPARENT), style=ft.ButtonStyle(shape=ft.CircleBorder(), overlay_color=ft.Colors.with_opacity(0.12, ft.Colors.ON_SURFACE)), on_click=lambda e: self._save_preset()),
                    ], spacing=6, tight=True),
                    ft.Container(height=24),
                    self.provider_textfield,
                    ft.Container(height=24),
                    self.base_url_textfield,
                    ft.Container(height=24),
                    self.api_key_textfield,
                    ft.Container(height=2),
                    ft.Row([self.review_enabled_switch, self.review_interval_field], spacing=4, tight=True),
                    ft.Row([
                        save_btn,
                        ft.TextButton("预设管理", style=ft.ButtonStyle(shape=ft.RoundedRectangleBorder(radius=12), bgcolor=ft.Colors.SURFACE_CONTAINER,
                     color=ft.Colors.ON_SURFACE), on_click=lambda e: self._open_preset_manager()),
                    ], spacing=8, tight=True),
                ], tight=True, spacing=6),
                bgcolor=ft.Colors.SURFACE_CONTAINER,
                
                border_radius=34,
                padding=18,
                border=ft.Border(top=ft.border.BorderSide(1, ft.Colors.with_opacity(0.06, ft.Colors.ON_SURFACE))),
            ),
            ft.Container(height=14),
            ft.Container(
                content=ft.Column([
                    ft.Row([ft.Icon(ft.Icons.LANGUAGE_ROUNDED, size=14, color=ft.Colors.PRIMARY), ft.Text(_("browser_control"), size=12, weight=ft.FontWeight.BOLD, color=ft.Colors.ON_SURFACE)], spacing=8, tight=True),
                    browser_hint,
                    ft.Container(height=6),
                    self.url_field,
                    ft.Column([
                        browser_open_btn,
                        browser_snapshot_btn,
                        browser_close_btn,
                    ], spacing=6, tight=True),
                ], tight=True, spacing=6),
                bgcolor=ft.Colors.SURFACE_CONTAINER,
                border_radius=34,
                padding=18,
                border=ft.Border(top=ft.border.BorderSide(1, ft.Colors.with_opacity(0.6, ft.Colors.OUTLINE_VARIANT))),
            ),
            ft.Container(height=14),
            ft.Container(
                content=ft.Column([
                    ft.Row([ft.Icon(ft.Icons.EXTENSION_ROUNDED, size=14, color=ft.Colors.PRIMARY), ft.Text("MCP 控制", size=12, weight=ft.FontWeight.BOLD, color=ft.Colors.ON_SURFACE)], spacing=8, tight=True),
                    ft.Container(height=14),
                    self.mcp_refresh_btn,
                    ft.Container(height=6),
                    ft.Text("已配置服务器", size=12, color=ft.Colors.ON_SURFACE),
                    self.mcp_server_list,
                    ft.Container(height=10),
                    ft.Text("运行状态", size=12, color=ft.Colors.ON_SURFACE),
                    self.mcp_status_list,
                ], tight=True, spacing=6),
                bgcolor=ft.Colors.SURFACE_CONTAINER,
                
                border_radius=34,
                padding=18,
                border=ft.Border(top=ft.border.BorderSide(1, ft.Colors.with_opacity(0.06, ft.Colors.ON_SURFACE))),
            ),
            ft.Container(height=14),
            ft.Container(
                content=ft.Column([
                    ft.Row([ft.Icon(ft.Icons.ACCOUNT_TREE_ROUNDED, size=14, color=ft.Colors.PRIMARY), ft.Text("工作流", size=12, weight=ft.FontWeight.BOLD, color=ft.Colors.ON_SURFACE)], spacing=8, tight=True),
                    ft.Container(height=14),
                    self.workflow_refresh_btn,
                    ft.Container(height=6),
                    ft.Text("预定义工作流", size=12, color=ft.Colors.ON_SURFACE),
                    self.workflow_list,
                ], tight=True, spacing=6),
                bgcolor=ft.Colors.SURFACE_CONTAINER,
                
                border_radius=34,
                padding=18,
                border=ft.Border(top=ft.border.BorderSide(1, ft.Colors.with_opacity(0.06, ft.Colors.ON_SURFACE))),
            ),
            ft.Container(height=14),
            ft.Container(
                content=ft.Column([
                    ft.Text("快捷提示词", size=13, weight=ft.FontWeight.BOLD, color=ft.Colors.ON_SURFACE),
                    ft.Icon(ft.Icons.LIGHTBULB_ROUNDED, size=14, color=ft.Colors.PRIMARY),
                    ft.Container(height=6),
                    self._build_prompt_templates(),
                    ft.Container(height=14),
                    ft.Divider(height=1, color=ft.Colors.OUTLINE_VARIANT, opacity=0.5),
                    ft.Container(height=14),
                    ft.Text(_("session_tab"), size=13, weight=ft.FontWeight.BOLD, color=ft.Colors.ON_SURFACE),
                    ft.Icon(ft.Icons.CHAT, size=14, color=ft.Colors.PRIMARY),
                    ft.Container(height=14),
                    ft.Row([self.session_name_field, self.session_save_btn], spacing=6),
                    ft.Container(height=6),
                    ft.Text("已保存会话", size=12, color=ft.Colors.ON_SURFACE),
                    ft.Divider(height=1, color=ft.Colors.OUTLINE_VARIANT, opacity=0.5),
                    self.session_list,
                ], tight=True, spacing=6),
                bgcolor=ft.Colors.SURFACE_CONTAINER,
                
                border_radius=34,
                padding=18,
                border=ft.Border(top=ft.border.BorderSide(1, ft.Colors.with_opacity(0.06, ft.Colors.ON_SURFACE))),
            ),
            ft.Container(height=14),
            ft.Container(
                content=ft.Column([
                    ft.Text("对话统计", size=13, weight=ft.FontWeight.BOLD, color=ft.Colors.ON_SURFACE),
                    ft.Icon(ft.Icons.SHOW_CHART_ROUNDED, size=14, color=ft.Colors.PRIMARY),
                    ft.Container(height=14),
                    ft.Row([ft.Text("调用次数", size=11, color=ft.Colors.ON_SURFACE_VARIANT), self.usage_calls_text], alignment=ft.MainAxisAlignment.SPACE_BETWEEN),
                    ft.Row([ft.Text("成功率", size=11, color=ft.Colors.ON_SURFACE_VARIANT), self.usage_success_text], alignment=ft.MainAxisAlignment.SPACE_BETWEEN),
                    ft.Row([ft.Text("平均延迟", size=11, color=ft.Colors.ON_SURFACE_VARIANT), self.usage_latency_text], alignment=ft.MainAxisAlignment.SPACE_BETWEEN),
                    ft.Row([ft.Text("Token 消耗", size=11, color=ft.Colors.ON_SURFACE_VARIANT), self.usage_tokens_text], alignment=ft.MainAxisAlignment.SPACE_BETWEEN),
                    ft.Row([ft.Text("估算成本", size=11, color=ft.Colors.ON_SURFACE_VARIANT), self.usage_cost_text], alignment=ft.MainAxisAlignment.SPACE_BETWEEN),
                    ft.Container(height=8),
                    ft.TextButton("刷新统计", style=ft.ButtonStyle(shape=ft.RoundedRectangleBorder(radius=12), bgcolor=ft.Colors.SURFACE_CONTAINER, color=ft.Colors.ON_SURFACE), on_click=lambda e: self._refresh_usage_dash()),
                ], tight=True, spacing=6),
                bgcolor=ft.Colors.SURFACE_CONTAINER,
                border_radius=34,
                padding=18,
                border=ft.Border(top=ft.border.BorderSide(1, ft.Colors.with_opacity(0.06, ft.Colors.ON_SURFACE))),
            ),
            ft.Container(height=14),
            ft.Container(
                content=ft.Column([
                    ft.Text(_("status_tab"), size=12, weight=ft.FontWeight.BOLD, color=ft.Colors.ON_SURFACE),
                    ft.Icon(ft.Icons.INFO, size=14, color=ft.Colors.PRIMARY),
                    ft.Container(height=14),
                    ft.Row([self.browser_status_icon, self.browser_status_text], spacing=10, alignment=ft.MainAxisAlignment.START),
                    ft.Row([self.status_text, self.perf_text, ft.Container(expand=True), self._clock_text], spacing=10),
                    ft.Container(height=8),
                    ft.Row([
                        ft.Icon(ft.Icons.AUTO_STORIES_ROUNDED, size=14, color=ft.Colors.PRIMARY),
                        ft.Text("后台复盘", size=11, color=ft.Colors.ON_SURFACE),
                        self.review_enabled_switch,
                        ft.Text(f"每 {self.review_interval_field.value} 轮", size=10, color=ft.Colors.ON_SURFACE_VARIANT),
                    ], spacing=8, tight=True),
                ], tight=True, spacing=6),
                bgcolor=ft.Colors.SURFACE_CONTAINER,
                
                border_radius=34,
                padding=18,
                border=ft.Border(top=ft.border.BorderSide(1, ft.Colors.with_opacity(0.06, ft.Colors.ON_SURFACE))),
            ),
            ft.Container(height=14),
            ft.Container(
                content=ft.Column([
                    ft.Row([ft.Text("角色人格", size=12, weight=ft.FontWeight.BOLD, color=ft.Colors.ON_SURFACE), ft.Icon(ft.Icons.PERSON_ROUNDED, size=14, color=ft.Colors.PRIMARY)], spacing=8, tight=True),
                    ft.Container(height=10),
                    self.persona_dropdown,
                    ft.Text("切换后独立记忆 + 系统提示词", size=11, color=ft.Colors.ON_SURFACE_VARIANT, opacity=0.85),
                ], tight=True, spacing=4),
                bgcolor=ft.Colors.SURFACE_CONTAINER,
                border_radius=34,
                padding=18,
                border=ft.Border(top=ft.border.BorderSide(1, ft.Colors.with_opacity(0.06, ft.Colors.ON_SURFACE))),
            ),
        ])
        return self._sidebar_container

    def _build_chat(self) -> ft.Column:
        self.chat_list = ft.ListView(expand=True, spacing=6, auto_scroll=True, scroll=ft.ScrollMode.AUTO, padding=ft.Padding(8, 4, 8, 4))
        self.input_field = ft.TextField(
            hint_text="输入消息...",
            expand=True,
            multiline=True,
            min_lines=1,
            max_lines=6,
            shift_enter=True,
            border_radius=34,
            border_color=ft.Colors.OUTLINE_VARIANT,
            focused_border_color=ft.Colors.OUTLINE_VARIANT,
            focused_border_width=1,
            suffix=ft.IconButton(icon=ft.Icons.CLEAR_ROUNDED, tooltip="清空输入", icon_color=ft.Colors.ON_SURFACE_VARIANT, on_click=lambda e: setattr(self.input_field, 'value', '') or self.page.update()),
        )
        self.input_count = ft.Text("0 字", size=12, color=ft.Colors.ON_SURFACE_VARIANT, opacity=0.95)
        self.input_field.on_change = lambda e: self._on_input_change()
        self._input_timer = None
        self._input_pending = False
        self.send_btn = ft.IconButton(icon=ft.Icons.SEND_ROUNDED, tooltip="发送", bgcolor=ft.Colors.PRIMARY, icon_color=ft.Colors.ON_PRIMARY, scale=1.0, disabled=True, style=ft.ButtonStyle(shape=ft.RoundedRectangleBorder(radius=12), elevation=3, shadow_color=ft.Colors.with_opacity(0.3, ft.Colors.PRIMARY), overlay_color=ft.Colors.with_opacity(0.15, ft.Colors.ON_PRIMARY)), animate_scale=ft.Animation(duration=150, curve=ft.AnimationCurve.EASE_IN_OUT))
        def _on_send_click(e):
            self.send_btn.scale = 0.92
            self.send_btn.update()
            self.send_btn.scale = 1.0
            self.send_btn.update()
            self._send()
        self.send_btn.on_click = _on_send_click
        self.send_btn.on_hover = lambda e: (self.send_btn.update() if not self.send_btn.disabled else None)
        self.stop_btn = ft.IconButton(icon=ft.Icons.STOP_ROUNDED, tooltip="停止生成", visible=False, bgcolor=ft.Colors.ERROR, icon_color=ft.Colors.ON_ERROR, style=ft.ButtonStyle(shape=ft.RoundedRectangleBorder(radius=12), overlay_color=ft.Colors.with_opacity(0.15, ft.Colors.ON_ERROR)), animate_scale=ft.Animation(duration=180, curve=ft.AnimationCurve.EASE_IN_OUT), animate_opacity=ft.Animation(duration=120, curve=ft.AnimationCurve.EASE_IN_OUT))
        self.stop_btn.on_click = lambda e: self._stop_send()
        self.input_field.on_submit = lambda e: self._send()
        self.voice_record_btn = ft.IconButton(icon=ft.Icons.MIC_ROUNDED, tooltip="语音输入", bgcolor=ft.Colors.SURFACE_CONTAINER, icon_color=ft.Colors.ON_SURFACE, style=ft.ButtonStyle(shape=ft.CircleBorder(), overlay_color=ft.Colors.with_opacity(0.12, ft.Colors.ON_SURFACE_VARIANT)), animate_scale=ft.Animation(duration=180, curve=ft.AnimationCurve.EASE_IN_OUT))
        self.voice_record_btn.on_click = lambda e: self._start_voice_input()
        self.voice_speak_btn = ft.IconButton(icon=ft.Icons.VOLUME_UP_ROUNDED, tooltip="语音播报", bgcolor=ft.Colors.SURFACE_CONTAINER, icon_color=ft.Colors.ON_SURFACE, style=ft.ButtonStyle(shape=ft.CircleBorder(), overlay_color=ft.Colors.with_opacity(0.12, ft.Colors.ON_SURFACE_VARIANT)), animate_scale=ft.Animation(duration=180, curve=ft.AnimationCurve.EASE_IN_OUT), visible=False)
        self.voice_speak_btn.on_click = lambda e: self._speak_last_reply()
        def _on_input_change():
            try:
                self._input_pending = True
                if self._input_timer:
                    self._input_timer.cancel()
                self._input_timer = self.page.run_task(self._apply_input_update)
            except Exception:
                logger.debug('desktop exception: %s', traceback.format_exc())
        self._on_input_change = _on_input_change
        clear_chat_btn = ft.TextButton("清屏", style=ft.ButtonStyle(shape=ft.RoundedRectangleBorder(radius=12), bgcolor=ft.Colors.ERROR_CONTAINER, color=ft.Colors.ON_ERROR_CONTAINER), icon=ft.Icons.DELETE_OUTLINE_ROUNDED, animate_scale=ft.Animation(duration=180, curve=ft.AnimationCurve.EASE_IN_OUT))
        clear_chat_btn.on_click = lambda e: self._clear_chat()
        
        self._chat_placeholder = ft.Column(
            [
                ft.Icon(ft.Icons.CHAT_BUBBLE_OUTLINE_ROUNDED, size=52, color=ft.Colors.ON_SURFACE_VARIANT, opacity=0.6, animate_scale=ft.Animation(duration=1200, curve=ft.AnimationCurve.EASE_IN_OUT)),
                ft.Container(height=14),
                ft.Text("输入消息开始对话", size=14, color=ft.Colors.ON_SURFACE_VARIANT, text_align=ft.TextAlign.CENTER, opacity=0.95),
            ],
            alignment=ft.MainAxisAlignment.CENTER,
            horizontal_alignment=ft.CrossAxisAlignment.CENTER,
        )
        self._init_error_banner = ft.Container(
            content=ft.Row(
                [
                    ft.Icon(ft.Icons.ERROR_ROUNDED, color=ft.Colors.ERROR),
                    ft.Text("", color=ft.Colors.ON_SURFACE_VARIANT, expand=True),
                    ft.IconButton(
                        icon=ft.Icons.REFRESH_ROUNDED,
                        tooltip="重试初始化",
                        icon_color=ft.Colors.ON_ERROR_CONTAINER,
                        bgcolor=ft.Colors.with_opacity(0, ft.Colors.TRANSPARENT),
                        style=ft.ButtonStyle(shape=ft.CircleBorder(), overlay_color=ft.Colors.with_opacity(0.15, ft.Colors.ON_ERROR_CONTAINER)),
                        on_click=lambda e: self._retry_init(),
                    ),
                ],
                spacing=10,
            ),
            bgcolor=ft.Colors.ERROR_CONTAINER,
            border_radius=12,
            padding=ft.Padding(14, 12, 14, 12),
            visible=False,
            animate=ft.Animation(duration=200, curve=ft.AnimationCurve.EASE_OUT),
        )
        self.chat_search_field = ft.TextField(hint_text="搜索消息...", width=260, border_radius=18, dense=True, border=ft.Border.all(1, ft.Colors.OUTLINE_VARIANT), content_padding=ft.Padding(10, 8, 10, 8), bgcolor=ft.Colors.SURFACE_CONTAINER)
        return ft.Column(
            [
                ft.Row([ft.Text(_("chat_tab"), size=22, weight=ft.FontWeight.BOLD, color=ft.Colors.ON_SURFACE), ft.Container(expand=True), ft.Row([self._clock_text], alignment=ft.MainAxisAlignment.END)], alignment=ft.MainAxisAlignment.SPACE_BETWEEN, spacing=14),
                self.chat_search_field,
                ft.Row([
                    ft.IconButton(icon=ft.Icons.SEARCH_ROUNDED, tooltip="搜索", icon_color=ft.Colors.PRIMARY, on_click=lambda e: self._search_messages(self.chat_search_field.value or "")),
                    ft.IconButton(icon=ft.Icons.ARROW_DOWNWARD_ROUNDED, tooltip="下一个", icon_color=ft.Colors.ON_SURFACE_VARIANT, on_click=lambda e: self._jump_to_next_match(self.chat_search_field.value or "")),
                    ft.IconButton(icon=ft.Icons.ARROW_UPWARD_ROUNDED, tooltip="上一个", icon_color=ft.Colors.ON_SURFACE_VARIANT, on_click=lambda e: self._prev_match(self.chat_search_field.value or "")),
                ], spacing=4, tight=True),
                ft.Divider(height=2, color=ft.Colors.OUTLINE_VARIANT, opacity=0.3),
                ft.Container(height=14),
                self._init_error_banner,
                self.chat_list,
                ft.Divider(height=2, color=ft.Colors.OUTLINE_VARIANT, opacity=0.3),
                ft.Container(
                    content=ft.Row([self.input_field, self.send_btn, self.stop_btn, self.voice_record_btn, self.voice_speak_btn], spacing=10, expand=True),
                    bgcolor=ft.Colors.SURFACE_CONTAINER,
                    
                    border_radius=34,
                    padding=ft.Padding(22, 20, 22, 20),
                    border=ft.Border(bottom=ft.border.BorderSide(2, ft.Colors.PRIMARY), left=ft.border.BorderSide(1, ft.Colors.OUTLINE_VARIANT), right=ft.border.BorderSide(1, ft.Colors.OUTLINE_VARIANT)),
                ),
                ft.Container(
                    height=2,
                    bgcolor=ft.Colors.TRANSPARENT,
                ),
                ft.Divider(height=1, color=ft.Colors.OUTLINE_VARIANT, opacity=0.25),
                ft.Row([clear_chat_btn, self.input_count], alignment=ft.MainAxisAlignment.SPACE_BETWEEN, spacing=8),
                ft.Container(height=6),
                ft.Text("Enter 发送 / Shift+Enter 换行", size=11, color=ft.Colors.ON_SURFACE_VARIANT, opacity=0.9),
            ],
            expand=True,
            spacing=6,
        )
    
    def _build_right_panel(self) -> ft.Column:
        self.terminal_input = ft.TextField(
            hint_text="输入终端命令...",
            expand=True,
            min_lines=1,
            max_lines=3,
            shift_enter=True,
            border_radius=34,
            focused_border_color=ft.Colors.PRIMARY,
            focused_border_width=2.5,
            border_color=ft.Colors.OUTLINE_VARIANT,
            suffix=ft.IconButton(icon=ft.Icons.CLEAR_ROUNDED, tooltip="清空终端", icon_size=18, icon_color=ft.Colors.ON_SURFACE_VARIANT, on_click=lambda e: self.terminal_input.clear()),
        )
        terminal_run_btn = ft.IconButton(icon=ft.Icons.PLAY_ARROW_ROUNDED, tooltip="执行命令", icon_color=ft.Colors.PRIMARY, bgcolor=ft.Colors.with_opacity(0, ft.Colors.TRANSPARENT), style=ft.ButtonStyle(shape=ft.CircleBorder(), overlay_color=ft.Colors.with_opacity(0.15, ft.Colors.PRIMARY)))
        terminal_run_btn.on_click = lambda e: self._run_terminal_command()
        self.terminal_input.on_submit = lambda e: self._run_terminal_command()
        self.terminal_list = ft.ListView(expand=True, spacing=4, auto_scroll=True, scroll=ft.ScrollMode.AUTO, padding=ft.Padding(6, 4, 6, 4))
        self.mcp_list = ft.ListView(expand=True, spacing=4, auto_scroll=True, scroll=ft.ScrollMode.AUTO, padding=ft.Padding(6, 4, 6, 4))
        
        clear_terminal_btn = ft.TextButton("清空终端", style=ft.ButtonStyle(shape=ft.RoundedRectangleBorder(radius=12), bgcolor=ft.Colors.ERROR_CONTAINER, color=ft.Colors.ON_ERROR_CONTAINER), icon=ft.Icons.DELETE_OUTLINE_ROUNDED, animate_scale=ft.Animation(duration=180, curve=ft.AnimationCurve.EASE_IN_OUT))
        clear_terminal_btn.on_click = lambda e: self._clear_terminal()
        clear_mcp_btn = ft.TextButton("清空 MCP", style=ft.ButtonStyle(shape=ft.RoundedRectangleBorder(radius=12), bgcolor=ft.Colors.ERROR_CONTAINER, color=ft.Colors.ON_ERROR_CONTAINER), icon=ft.Icons.DELETE_OUTLINE_ROUNDED, animate_scale=ft.Animation(duration=180, curve=ft.AnimationCurve.EASE_IN_OUT))
        clear_mcp_btn.on_click = lambda e: self._clear_mcp()
        retry_init_btn = ft.TextButton("重试初始化", style=ft.ButtonStyle(shape=ft.RoundedRectangleBorder(radius=12), bgcolor=ft.Colors.AMBER_100, color=ft.Colors.BLACK, icon_color=ft.Colors.BLACK), icon=ft.Icons.REFRESH_ROUNDED, animate_scale=ft.Animation(duration=180, curve=ft.AnimationCurve.EASE_IN_OUT))
        retry_init_btn.on_click = lambda e: self._retry_init()
        if getattr(self, "_init_error", None) is None:
            retry_init_btn.visible = False
        self.retry_init_btn = retry_init_btn
        
        terminal_tab = ft.Column(
            [
                ft.Row([self.terminal_input, terminal_run_btn], spacing=8),
                ft.Row([self.retry_init_btn, clear_terminal_btn], alignment=ft.MainAxisAlignment.END, spacing=8),
                ft.Container(self.terminal_list, expand=True, border=ft.Border.all(1, ft.Colors.OUTLINE_VARIANT), border_radius=34, padding=ft.Padding(18, 14, 18, 14), bgcolor=ft.Colors.SURFACE),
            ],
            expand=True,
            spacing=8,
        )
        mcp_tab = ft.Column(
            [
                ft.Text("MCP", size=13, weight=ft.FontWeight.W_600, color=ft.Colors.ON_SURFACE, opacity=0.95),
                ft.Row([clear_mcp_btn], alignment=ft.MainAxisAlignment.END),
                ft.Container(self.mcp_list, expand=True, border=ft.Border.all(1, ft.Colors.OUTLINE_VARIANT), border_radius=34, padding=ft.Padding(18, 14, 18, 14), bgcolor=ft.Colors.SURFACE),
            ],
            expand=True,
            spacing=8,
        )
        self._right_terminal_tab = terminal_tab
        self._right_mcp_tab = mcp_tab
        self._right_skills_tab = ft.Column(
            [
                ft.Row([ft.Text(_("refresh_skills"), size=12, weight=ft.FontWeight.BOLD, color=ft.Colors.ON_SURFACE), ft.Container(expand=True), self.skill_search], alignment=ft.MainAxisAlignment.SPACE_BETWEEN, spacing=8),
                ft.Row([self.skill_install_field, self.skill_install_btn], spacing=8),
                ft.Container(self.skill_list, expand=True, border=ft.Border.all(1, ft.Colors.OUTLINE_VARIANT), border_radius=34, padding=ft.Padding(18, 14, 18, 14), bgcolor=ft.Colors.SURFACE),
                ft.Divider(height=1, color=ft.Colors.OUTLINE_VARIANT, opacity=0.25),
                ft.Row([ft.Text(_("skill_hub_browse"), size=12, weight=ft.FontWeight.BOLD, color=ft.Colors.ON_SURFACE), ft.Container(expand=True)], alignment=ft.MainAxisAlignment.START, spacing=8),
                ft.Row([self.hub_search, self.hub_browse_btn], spacing=8),
                ft.Container(self.hub_list, expand=True, border=ft.Border.all(1, ft.Colors.OUTLINE_VARIANT), border_radius=34, padding=ft.Padding(18, 14, 18, 14), bgcolor=ft.Colors.SURFACE),
            ],
            expand=True,
            spacing=8,
        )
        self._right_workflow_tab = ft.Column(
            [
                ft.Row([ft.Text("工作流", size=12, weight=ft.FontWeight.BOLD, color=ft.Colors.ON_SURFACE), ft.Container(expand=True)], alignment=ft.MainAxisAlignment.START, spacing=8),
                self.workflow_refresh_btn,
                ft.Container(self.workflow_list, expand=True, border=ft.Border.all(1, ft.Colors.OUTLINE_VARIANT), border_radius=34, padding=ft.Padding(18, 14, 18, 14), bgcolor=ft.Colors.SURFACE),
            ],
            expand=True,
            spacing=8,
        )
        self._right_message_tab = ft.Column(
            [
                ft.Row([ft.Text("消息", size=13, weight=ft.FontWeight.BOLD, color=ft.Colors.ON_SURFACE, opacity=0.95), ft.Container(expand=True), ft.Row([ft.TextButton("刷新", on_click=lambda e: self._refresh_message_store())], spacing=4, tight=True)], alignment=ft.MainAxisAlignment.SPACE_BETWEEN, spacing=8),
                ft.Container(self.message_store_list, expand=True, border=ft.Border.all(1, ft.Colors.OUTLINE_VARIANT), border_radius=34, padding=ft.Padding(18, 14, 18, 14), bgcolor=ft.Colors.SURFACE),
            ],
            expand=True,
            spacing=8,
        )
        self.message_store_list = ft.ListView(expand=True, spacing=4, auto_scroll=True, scroll=ft.ScrollMode.AUTO, padding=ft.Padding(6, 4, 6, 4))
        self._right_retry_tab = ft.Column(
            [
                ft.Row([ft.Text("重试", size=13, weight=ft.FontWeight.BOLD, color=ft.Colors.ON_SURFACE, opacity=0.95), ft.Container(expand=True)], alignment=ft.MainAxisAlignment.START, spacing=8),
                ft.Container(self.retry_list, expand=True, border=ft.Border.all(1, ft.Colors.OUTLINE_VARIANT), border_radius=34, padding=ft.Padding(18, 14, 18, 14), bgcolor=ft.Colors.SURFACE),
            ],
            expand=True,
            spacing=8,
        )
        self.retry_list = ft.ListView(expand=True, spacing=4, auto_scroll=True, scroll=ft.ScrollMode.AUTO, padding=ft.Padding(6, 4, 6, 4))
        self._right_webhook_tab = ft.Column(
            [
                ft.Row([ft.Text("Webhook", size=13, weight=ft.FontWeight.BOLD, color=ft.Colors.ON_SURFACE, opacity=0.95), ft.Container(expand=True), ft.Row([ft.TextButton("启动服务", on_click=lambda e: self._start_webhook_server())], spacing=4, tight=True)], alignment=ft.MainAxisAlignment.SPACE_BETWEEN, spacing=8),
                ft.Container(self.webhook_list, expand=True, border=ft.Border.all(1, ft.Colors.OUTLINE_VARIANT), border_radius=34, padding=ft.Padding(18, 14, 18, 14), bgcolor=ft.Colors.SURFACE),
            ],
            expand=True,
            spacing=8,
        )
        self.webhook_list = ft.ListView(expand=True, spacing=4, auto_scroll=True, scroll=ft.ScrollMode.AUTO, padding=ft.Padding(6, 4, 6, 4))
        self._right_schedule_tab = ft.Column(
            [
                ft.Row([ft.Text("定时", size=13, weight=ft.FontWeight.BOLD, color=ft.Colors.ON_SURFACE, opacity=0.95), ft.Container(expand=True), ft.Row([ft.TextButton("同步", on_click=lambda e: self._refresh_schedule())], spacing=4, tight=True)], alignment=ft.MainAxisAlignment.SPACE_BETWEEN, spacing=8),
                ft.Container(self.schedule_list, expand=True, border=ft.Border.all(1, ft.Colors.OUTLINE_VARIANT), border_radius=34, padding=ft.Padding(18, 14, 18, 14), bgcolor=ft.Colors.SURFACE),
            ],
            expand=True,
            spacing=8,
        )
        self.schedule_list = ft.ListView(expand=True, spacing=4, auto_scroll=True, scroll=ft.ScrollMode.AUTO, padding=ft.Padding(6, 4, 6, 4))
        self._right_notification_tab = ft.Column(
            [
                ft.Row([ft.Text("通知", size=13, weight=ft.FontWeight.BOLD, color=ft.Colors.ON_SURFACE, opacity=0.95), ft.Container(expand=True)], alignment=ft.MainAxisAlignment.SPACE_BETWEEN, spacing=8),
                ft.Container(self.notification_list, expand=True, border=ft.Border.all(1, ft.Colors.OUTLINE_VARIANT), border_radius=34, padding=ft.Padding(18, 14, 18, 14), bgcolor=ft.Colors.SURFACE),
            ],
            expand=True,
            spacing=8,
        )
        self.notification_list = ft.ListView(expand=True, spacing=4, auto_scroll=True, scroll=ft.ScrollMode.AUTO, padding=ft.Padding(6, 4, 6, 4))
        # Right panel tabs
        self._right_tab_buttons_row = ft.Row([], spacing=2, tight=True)
        self._right_tab_contents = ft.Column([terminal_tab, mcp_tab, self._right_skills_tab, self._right_workflow_tab, self._right_message_tab, self._right_retry_tab, self._right_webhook_tab, self._right_schedule_tab, self._right_notification_tab], expand=True, spacing=0)
        for idx, label in enumerate(["终端", "MCP", "Skills", "工作流", "消息", "重试", "Webhook", "定时", "通知"]):
            btn = ft.TextButton(
                label,
                style=ft.ButtonStyle(
                    shape=ft.RoundedRectangleBorder(radius=10),
                    bgcolor=ft.Colors.PRIMARY_CONTAINER if idx == 0 else ft.Colors.SURFACE_CONTAINER,
                    color=ft.Colors.ON_PRIMARY_CONTAINER if idx == 0 else ft.Colors.ON_SURFACE,
                    padding=ft.Padding(10, 6, 10, 6),
                ),
                on_click=lambda e, i=idx: self._switch_right_tab(i),
            )
            self._right_tab_buttons_row.controls.append(btn)
        self._right_tab_contents.visible = True
        self._right_tab_contents.opacity = 1.0
        self._right_tab_contents.scroll = ft.ScrollMode.AUTO
        self._active_right_tab_index = 0

        def _show_tab(index: int):
            self._active_right_tab_index = index
            for i, ctrl in enumerate(self._right_tab_contents.controls):
                if i == index:
                    ctrl.visible = True
                    ctrl.opacity = 1.0
                    ctrl.disabled = False
                else:
                    ctrl.visible = True
                    ctrl.opacity = 0.0
                    ctrl.disabled = True
            for i, btn in enumerate(self._right_tab_buttons_row.controls):
                btn.style = ft.ButtonStyle(
                    shape=ft.RoundedRectangleBorder(radius=10),
                    bgcolor=ft.Colors.PRIMARY_CONTAINER if i == index else ft.Colors.SURFACE_CONTAINER,
                    color=ft.Colors.ON_PRIMARY_CONTAINER if i == index else ft.Colors.ON_SURFACE,
                    padding=ft.Padding(10, 6, 10, 6),
                )
            if index == 2 and hasattr(self, "_refresh_skills"):
                try:
                    self._refresh_skills()
                except Exception:
                    pass
            try:
                self._right_tab_contents.update()
                self._right_tab_buttons_row.update()
            except Exception:
                pass

        self._switch_right_tab = lambda i: _show_tab(i)
        _show_tab(0)

        return ft.Column(
            [
                self._right_tab_buttons_row,
                self._right_tab_contents,
            ],
            expand=True,
            spacing=8,
        )
    
    def _append(self, role: str, text: str, retry: bool = False, retry_text: str = "", placeholder: bool = False):
        if hasattr(self, "_chat_placeholder") and self._chat_placeholder:
            try:
                self._chat_placeholder.visible = False
                parent = getattr(self._chat_placeholder, "parent", None)
                if parent is not None:
                    parent.visible = False
                    parent.update()
                if self._chat_placeholder in self.chat_list.controls:
                    self.chat_list.controls.remove(self._chat_placeholder)
            except Exception:
                logger.debug("hide placeholder failed: %s", traceback.format_exc())
        is_user = role == "你"
        align = ft.MainAxisAlignment.END if is_user else ft.MainAxisAlignment.START
        text_color = ft.Colors.ON_PRIMARY_CONTAINER if is_user else ft.Colors.ON_SURFACE
        timestamp = datetime.now().strftime("%H:%M")
        try:
            role_text = ft.Text(role, size=11, color=ft.Colors.ON_SURFACE_VARIANT, weight=ft.FontWeight.W_500)
            time_text = ft.Text(timestamp, size=11, color=ft.Colors.ON_SURFACE_VARIANT, opacity=0.8)
            content = self._markdown_to_ft(text)
            row = ft.Row(
                [role_text, ft.Container(expand=True), time_text],
                alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
            )
            message_widget = ft.Container(
                content=ft.Column(
                    [row, ft.Container(height=4), *content],
                    tight=True,
                    spacing=0,
                    horizontal_alignment=align,
                ),
                padding=ft.Padding(14, 10, 14, 10),
                bgcolor=ft.Colors.PRIMARY_CONTAINER if is_user else ft.Colors.SURFACE_CONTAINER,
            )
            self.chat_list.controls.append(message_widget)
            try:
                self.chat_list.update()
            except Exception:
                logger.debug("chat_list update failed: %s", traceback.format_exc())
            try:
                self.page.update()
            except Exception:
                logger.debug("page update failed: %s", traceback.format_exc())
        except Exception:
            logger.debug("append message failed: %s", traceback.format_exc())
            try:
                self._append_terminal(f"[CHAT ERROR] {role}: {text[:200]}")
            except Exception as ex:
                logger.debug("append message fallback failed: %s", ex)


    def _new_session(self):
        self._current_session_name = None
        self._settings["current_session"] = None
        self.chat_list.controls.clear()
        if hasattr(self, "_chat_placeholder") and self._chat_placeholder:
            self._chat_placeholder.visible = True
            self.chat_list.controls.append(self._chat_placeholder)
        self.chat_list.update()
        self.input_field.value = ""
        self.input_field.focus()
        self._update_input_count()
        self._set_status("新对话")
        self._append_terminal("new session")

    def _save_session(self):
        def _run():
            try:
                name = self._current_session_name or f"session_{int(time.time())}"
                path = self.agent.save_session(name)
                self._append_terminal(f"session saved: {path}")
                self._set_status("会话已保存", ft.Colors.GREEN_400)
                self._settings["current_session"] = name
                self._refresh_sessions()
            except Exception as e:
                self._append_terminal(f"session save failed: {e}")
                self._set_status("会话保存失败", ft.Colors.RED_400)
        try:
            self.page.run_task(_run)
        except Exception:
            _run()

    def _refresh_sessions(self):
        def _run():
            self.session_list.controls.clear()
            try:
                names = self.agent.list_sessions()
            except Exception as exc:
                self._log_error("list sessions", exc)
                names = []
            pinned = self._settings.get("pinned_sessions", {}) or {}
            names = sorted(names, key=lambda n: (not pinned.get(n, False), n))
            if not names:
                self.session_list.controls.append(self._session_empty_state)
            else:
                for name in names:
                    is_current = name == self._current_session_name
                    pin_btn = ft.IconButton(
                        icon=ft.Icons.PUSH_PIN_ROUNDED if pinned.get(name) else ft.Icons.PUSH_PIN_OUTLINE_ROUNDED,
                        tooltip="置顶" if pinned.get(name) else "取消置顶",
                        icon_color=ft.Colors.ON_SURFACE_VARIANT,
                        width=36,
                        height=36,
                    )
                    pin_btn.on_click = lambda e, n=name: self._toggle_pin_session(n)
                    rename_btn = ft.IconButton(icon=ft.Icons.EDIT_OUTLINE, tooltip="重命名", icon_color=ft.Colors.ON_SURFACE_VARIANT, width=36, height=36)
                    rename_btn.on_click = lambda e, n=name: self._rename_session(n)
                    load_btn = ft.Button(
                        name,
                        expand=True,
                        style=ft.ButtonStyle(
                            bgcolor=ft.Colors.PRIMARY_CONTAINER if is_current else None,
                            color=ft.Colors.ON_PRIMARY_CONTAINER if is_current else None,
                            shape=ft.RoundedRectangleBorder(radius=8),
                            padding=ft.Padding(22, 20, 22, 20),
                        ),
                    )
                    load_btn.on_click = lambda e, n=name: self._load_session(n)
                    del_btn = ft.IconButton(icon=ft.Icons.DELETE_OUTLINE, tooltip="删除会话", icon_color=ft.Colors.ERROR, width=36, height=36)
                    del_btn.on_click = lambda e, n=name: self._delete_session(n)
                    export_btn = ft.IconButton(icon=ft.Icons.DOWNLOAD_OUTLINED, tooltip="导出 Markdown", icon_color=ft.Colors.ON_SURFACE_VARIANT, width=36, height=36)
                    export_btn.on_click = lambda e, n=name: self._export_session(n)
                    session_row = ft.Row([pin_btn, load_btn, rename_btn, export_btn, del_btn], spacing=6, tight=True)
                    session_row._session_name = name
                    session_wrap = ft.Container(
                        content=session_row,
                        padding=ft.Padding(4, 4, 4, 4),
                        border_radius=10,
                        bgcolor=ft.Colors.TRANSPARENT,
                        animate=ft.Animation(duration=120, curve=ft.AnimationCurve.EASE_OUT),
                    )
                    def _on_session_hover(e, w=session_wrap):
                        w.bgcolor = ft.Colors.with_opacity(0.08, ft.Colors.ON_SURFACE) if e.data == 'true' else ft.Colors.TRANSPARENT
                        try:
                            w.update()
                        except Exception:
                            logger.debug("session hover update failed: %s", traceback.format_exc())
                    session_wrap.on_hover = _on_session_hover
                    self._session_all_items.append(session_row)
                    self.session_list.controls.append(session_wrap)
            self.session_list.update()
        try:
            self.page.run_task(_run)
        except Exception:
            _run()

    def _delete_session(self, name: str):
        def _run():
            try:
                ok = self.agent.delete_session(name)
                if ok and name == self._current_session_name:
                    self._current_session_name = None
                self._append_terminal(f"session delete {name}: {'ok' if ok else 'failed'}")
                self._set_status("会话已删除" if ok else "删除失败", ft.Colors.GREEN_400 if ok else ft.Colors.RED_400)
            except Exception as e:
                self._append_terminal(f"session delete error: {e}")
                self._set_status("删除异常", ft.Colors.RED_400)
            self._refresh_sessions()
        try:
            self.page.run_task(_run)
        except Exception:
            _run()

    def _export_session(self, name: str):
        def _run():
            try:
                session = self.agent.load_session(name)
                messages = getattr(session, "messages", [])
                lines = [f"# PRISM Session: {name}", ""]
                for m in messages:
                    role = m.role if hasattr(m, "role") else getattr(m, "role", "unknown")
                    content = m.content if hasattr(m, "content") else getattr(m, "content", "")
                    if role == "system":
                        continue
                    label = "你" if role == "user" else ("PRISM" if role == "assistant" else role)
                    lines.append(f"## {label}")
                    lines.append(content or "")
                    lines.append("")
                path = os.path.join(self.agent.session_dir, f"{name}.md")
                with open(path, "w", encoding="utf-8") as f:
                    f.write("\n".join(lines))
                self._append_terminal(f"session exported: {path}")
                self._set_status("会话已导出", ft.Colors.GREEN_400)
            except Exception as exc:
                self._log_error("session export", exc)
                self._set_status("导出失败", ft.Colors.RED_400)
        try:
            self.page.run_task(_run)
        except Exception:
            _run()

    def _toggle_pin_session(self, name: str):
        pinned = self._settings.get("pinned_sessions", {}) or {}
        pinned[name] = not pinned.get(name, False)
        self._settings["pinned_sessions"] = pinned
        self._save_settings_debounced()
        self._refresh_sessions()

    def _rename_session(self, name: str):
        def on_submit(e):
            new_name = (rename_field.value or "").strip()
            if not new_name:
                self._set_status("名称不能为空", ft.Colors.RED_400)
                return
            if new_name != name:
                try:
                    ok = self.agent.rename_session(name, new_name)
                    if ok:
                        if self._current_session_name == name:
                            self._current_session_name = new_name
                        self._refresh_sessions()
                        self._set_status(f"已重命名为: {new_name}")
                    else:
                        self._set_status("重命名失败", ft.Colors.RED_400)
                except Exception as e:
                    self._set_status(f"重命名异常: {e}", ft.Colors.RED_400)
            dialog.open = False
            self.page.update()

        rename_field = ft.TextField(value=name, label="新会话名称", border_radius=34, autofocus=True)
        rename_field.on_submit = on_submit
        dialog = ft.AlertDialog(
            title=ft.Text("重命名会话"),
            content=rename_field,
            actions=[
                ft.TextButton("取消", on_click=lambda e: (setattr(dialog, "open", False), self.page.update())),
                ft.TextButton("确定", on_click=on_submit),
            ],
        )
        self.page.dialog = dialog
        dialog.open = True
        self.page.update()

    def _load_session(self, name: str):
        try:
            ok = self.agent.load_session(name)
            if ok:
                self._current_session_name = name
                self._settings["current_session"] = name
                self._append_terminal(f"session loaded: {name}")
                self._set_status("会话已加载")
                self.chat_list.controls.clear()
                for m in self.agent.messages:
                    if m.role == "system":
                        continue
                    role_label = "你" if m.role == "user" else ("PRISM" if m.role == "assistant" else m.role)
                    self._append(role_label, m.content or "")
                self.chat_list.update()
        except Exception as exc:
            self._log_error("session load", exc)
            self._set_status("加载失败", ft.Colors.RED_400)

    def _refresh_message_store(self):
        def _run():
            self.message_store_list.controls.clear()
            try:
                from prism.message_store import message_store
                items = message_store.history(getattr(self, "_current_session_name", "") or "")
            except Exception:
                items = []
            if not items:
                self.message_store_list.controls.append(ft.Text("无消息", color=ft.Colors.ON_SURFACE_VARIANT))
            for item in items[-200:]:
                text = f"{item.get('role','')} {item.get('content','')[:80]}"
                row = ft.Row([ft.Text(text, size=12, color=ft.Colors.ON_SURFACE_VARIANT)], spacing=8)
                self.message_store_list.controls.append(row)
            try:
                self.message_store_list.update()
            except Exception:
                pass
        try:
            self.page.run_task(_run)
        except Exception:
            _run()

    def _refresh_retry_queue(self):
        def _run():
            self.retry_list.controls.clear()
            try:
                from prism.retry_strategy import retry_strategy
                tasks = retry_strategy.due()
            except Exception:
                tasks = []
            if not tasks:
                self.retry_list.controls.append(ft.Text("无待重试任务", color=ft.Colors.ON_SURFACE_VARIANT))
            for task in tasks:
                text = f"{task.id} attempts={task.attempts}/{task.max_attempts} error={task.last_error[:40]}"
                row = ft.Row([ft.Text(text, size=12, color=ft.Colors.ON_SURFACE_VARIANT)], spacing=8)
                self.retry_list.controls.append(row)
            try:
                self.retry_list.update()
            except Exception:
                pass
        try:
            self.page.run_task(_run)
        except Exception:
            _run()

    def _start_webhook_server(self):
        try:
            from prism.webhook_trigger import webhook_trigger
            thread = webhook_trigger.start_server(port=9900)
            self._append_terminal("webhook server started on 127.0.0.1:9900")
            self._set_status("Webhook 已启动", ft.Colors.GREEN_400)
        except Exception as exc:
            self._log_error("webhook start", exc)
            self._set_status("Webhook 启动失败", ft.Colors.RED_400)

    def _refresh_schedule(self):
        def _run():
            self.schedule_list.controls.clear()
            try:
                from prism.schedule_visualizer import schedule_visualizer
                widgets = schedule_visualizer.to_timeline_widgets(days=7)
            except Exception:
                widgets = []
            if not widgets:
                self.schedule_list.controls.append(ft.Text("无定时任务", color=ft.Colors.ON_SURFACE_VARIANT))
            for item in widgets:
                title = item.get("title", "")
                time = item.get("time", "")
                status = item.get("status", "")
                row = ft.Row([ft.Text(f"{title} {time}", size=12, color=ft.Colors.ON_SURFACE_VARIANT), ft.Text(status, size=11, color=ft.Colors.GREEN_400)], spacing=8)
                self.schedule_list.controls.append(row)
            try:
                self.schedule_list.update()
            except Exception:
                pass
        try:
            self.page.run_task(_run)
        except Exception:
            _run()


    def _append_terminal(self, text: str):
        self._terminal_lines.append(text)
        if len(self._terminal_lines) > 300:
            self._terminal_lines = self._terminal_lines[-300:]
        if not hasattr(self, "terminal_list") or self.terminal_list is None or not hasattr(self.terminal_list, "page") or self.terminal_list.page is None:
            return
        color = ft.Colors.ON_SURFACE_VARIANT
        if 'error' in text.lower() or '失败' in text or '错误' in text:
            color = ft.Colors.ERROR
        elif 'warn' in text.lower() or '警告' in text:
            color = ft.Colors.AMBER_400
        elif 'success' in text.lower() or '成功' in text or 'saved' in text.lower():
            color = ft.Colors.GREEN_400
        elif 'info' in text.lower() or '信息' in text:
            color = ft.Colors.BLUE_400
        line = ft.Text(text, size=12, color=color, selectable=True, font_family="Consolas, Monaco, monospace", height=18, opacity=0, animate_opacity=ft.Animation(duration=120, curve=ft.AnimationCurve.EASE_OUT))
        self.terminal_list.controls.append(line)
        line.opacity = 1
        try:
            self.terminal_list.update()
        except Exception:
            pass

    def _append_mcp(self, text: str):
        self._mcp_logs.append(text)
        if len(self._mcp_logs) > 200:
            self._mcp_logs = self._mcp_logs[-200:]
        if not hasattr(self, "mcp_list") or self.mcp_list is None or not hasattr(self.mcp_list, "page") or self.mcp_list.page is None:
            return
        self.mcp_list.controls.clear()
        for line in self._mcp_logs[-80:]:
            item = ft.Text(line, size=12, color=ft.Colors.ON_SURFACE, selectable=True, font_family="Consolas, Monaco, monospace", height=18, opacity=0, animate_opacity=ft.Animation(duration=100, curve=ft.AnimationCurve.EASE_OUT))
            item.opacity = 1
            self.mcp_list.controls.append(item)
        try:
            self.mcp_list.update()
        except Exception:
            pass

    def _clear_terminal(self):
        self._terminal_lines = []
        if hasattr(self, "terminal_list") and self.terminal_list is not None and hasattr(self.terminal_list, "page") and self.terminal_list.page is not None:
            self.terminal_list.controls.clear()
            try:
                self.terminal_list.update()
            except Exception:
                pass

    def _clear_mcp(self):
        self._mcp_logs = []
        if hasattr(self, "mcp_list") and self.mcp_list is not None and hasattr(self.mcp_list, "page") and self.mcp_list.page is not None:
            self.mcp_list.controls.clear()
            try:
                self.mcp_list.update()
            except Exception:
                pass


    def _refresh_skills(self):
        if not hasattr(self, "skill_list") or self.skill_list is None:
            return
        self._append_terminal("refresh skills ...")
        try:
            from prism.skills import skills
            skill_list = skills.list_skills()
            self._skill_all_items = list(skill_list)
            self._render_skill_items(self._skill_all_items)
            self._append_terminal(f"skills refreshed: {len(skill_list)} 个")
        except Exception as e:
            self._append_terminal(f"skills error: {e}")
            self._set_status("Skills 刷新失败", ft.Colors.RED_400)

    def _render_skill_items(self, skill_list):
        if not hasattr(self, "skill_list") or self.skill_list is None:
            return
        self.skill_list.controls.clear()
        if not skill_list:
            self.skill_list.controls.append(ft.Container(
                content=ft.Column([
                    ft.Icon(ft.Icons.EXTENSION_OFF_ROUNDED, size=28, color=ft.Colors.ON_SURFACE_VARIANT, opacity=0.5),
                    ft.Text("暂无 Skills", size=12, color=ft.Colors.ON_SURFACE_VARIANT, opacity=0.95),
                ], alignment=ft.MainAxisAlignment.CENTER, horizontal_alignment=ft.CrossAxisAlignment.CENTER, tight=True),
                padding=ft.Padding(48, 48, 48, 48),
                border_radius=12,
                bgcolor=ft.Colors.with_opacity(0.6, ft.Colors.SURFACE_CONTAINER),
            ))
        else:
            for skill in skill_list:
                status = _("skill_enabled") if skill.get('enabled') else _("skill_disabled")
                status_color = ft.Colors.GREEN_400 if skill.get('enabled') else ft.Colors.ON_SURFACE_VARIANT
                row = ft.Row([
                    ft.Column([
                        ft.Text(skill.get('name', 'unknown'), size=12, weight=ft.FontWeight.W_500, color=ft.Colors.ON_SURFACE),
                        ft.Text(skill.get('description', ''), size=10, color=ft.Colors.ON_SURFACE_VARIANT, opacity=0.85, max_lines=1, overflow=ft.TextOverflow.ELLIPSIS),
                    ], spacing=2, expand=True),
                    ft.Text(status, size=10, color=status_color, weight=ft.FontWeight.W_500),
                    ft.IconButton(icon=ft.Icons.POWER_SETTINGS_NEW_ROUNDED, tooltip=_("skill_toggle"), icon_size=14, icon_color=ft.Colors.ON_SURFACE_VARIANT, bgcolor=ft.Colors.with_opacity(0, ft.Colors.TRANSPARENT), style=ft.ButtonStyle(shape=ft.CircleBorder(), overlay_color=ft.Colors.with_opacity(0.12, ft.Colors.ON_SURFACE_VARIANT)), on_click=lambda e, n=skill.get('name'): self._toggle_skill(n)),
                    ft.IconButton(icon=ft.Icons.DELETE_OUTLINE_ROUNDED, tooltip=_("skill_uninstall"), icon_size=14, icon_color=ft.Colors.ON_SURFACE_VARIANT, bgcolor=ft.Colors.with_opacity(0, ft.Colors.TRANSPARENT), style=ft.ButtonStyle(shape=ft.CircleBorder(), overlay_color=ft.Colors.with_opacity(0.12, ft.Colors.ON_SURFACE_VARIANT)), on_click=lambda e, n=skill.get('name'): self._uninstall_skill(n)),
                ], spacing=6, tight=True)
                self.skill_list.controls.append(row)
        self.skill_list.update()

    def _filter_skills(self, text: str):
        q = (text or "").strip().lower()
        if not q:
            self._render_skill_items(self._skill_all_items)
            return
        filtered = [s for s in self._skill_all_items if q in s.get('name', '').lower() or q in s.get('description', '').lower() or any(q in t.lower() for t in s.get('triggers', []))]
        self._render_skill_items(filtered)

    def _toggle_skill(self, name: str):
        if not name:
            return
        self._append_terminal(f"toggle skill: {name}")
        try:
            from prism.skills import skills
            result = skills.toggle_skill(name)
            if result.get('success'):
                self._set_status(result.get('message', '已切换'), ft.Colors.GREEN_400)
                self._append_terminal(f"toggled: {result.get('message')}")
                self._refresh_skills()
            else:
                self._set_status(f"切换失败: {result.get('error', 'unknown')}", ft.Colors.RED_400)
        except Exception as e:
            self._append_terminal(f"toggle error: {e}")
            self._set_status("Skill 切换异常", ft.Colors.RED_400)

    def _install_skill_from_hub(self, name: str):
        if not name:
            return
        self._append_terminal(f"install from hub: {name}")
        try:
            from prism.skills import skills
            result = skills.install_skill(name)
            if result.get('success'):
                self._set_status(result.get('message', '安装成功'), ft.Colors.GREEN_400)
                self._append_terminal(f"installed from hub: {result.get('message')}")
                self._refresh_skills()
            else:
                self._set_status(f"安装失败: {result.get('error', 'unknown')}", ft.Colors.RED_400)
        except Exception as e:
            self._append_terminal(f"install hub error: {e}")
            self._set_status("Skill 安装异常", ft.Colors.RED_400)

    def _browse_hub_skills(self):
        q = (self.hub_search.value if hasattr(self, "hub_search") and self.hub_search else "").strip()
        self._append_terminal(f"browse hub skills: {q or '*'}")
        try:
            from prism.skills import skills
            data = skills.search_hub(q) if q else skills.browse_hub()
            self._render_hub_items(data)
        except Exception as e:
            self._append_terminal(f"hub browse error: {e}")
            self._set_status(_("skill_hub_error"), ft.Colors.RED_400)

    def _render_hub_items(self, items):
        if not hasattr(self, "hub_list") or self.hub_list is None:
            return
        self.hub_list.controls.clear()
        if not items:
            self.hub_list.controls.append(ft.Container(
                content=ft.Column([
                    ft.Icon(ft.Icons.PUBLIC_OFF_ROUNDED, size=28, color=ft.Colors.ON_SURFACE_VARIANT, opacity=0.5),
                    ft.Text(_("skill_hub_empty"), size=12, color=ft.Colors.ON_SURFACE_VARIANT, opacity=0.95),
                ], alignment=ft.MainAxisAlignment.CENTER, horizontal_alignment=ft.CrossAxisAlignment.CENTER, tight=True),
                padding=ft.Padding(48, 48, 48, 48),
                border_radius=12,
                bgcolor=ft.Colors.with_opacity(0.6, ft.Colors.SURFACE_CONTAINER),
            ))
        else:
            for item in items:
                row = ft.Row([
                    ft.Column([
                        ft.Text(item.get('name', 'unknown'), size=12, weight=ft.FontWeight.W_500, color=ft.Colors.ON_SURFACE),
                        ft.Text(item.get('description', ''), size=10, color=ft.Colors.ON_SURFACE_VARIANT, opacity=0.85, max_lines=1, overflow=ft.TextOverflow.ELLIPSIS),
                    ], spacing=2, expand=True),
                    ft.TextButton(_("skill_hub_install"), style=ft.ButtonStyle(shape=ft.RoundedRectangleBorder(radius=12), bgcolor=ft.Colors.PRIMARY_CONTAINER, color=ft.Colors.ON_PRIMARY_CONTAINER), on_click=lambda e, n=item.get('name'): self._install_skill_from_hub(n)),
                ], spacing=8, tight=True)
                self.hub_list.controls.append(row)
        self.hub_list.update()

    def _uninstall_skill(self, name: str):
        if not name:
            return
        self._append_terminal(f"uninstall skill: {name}")
        try:
            from prism.skills import skills
            result = skills.uninstall_skill(name)
            if result.get('success'):
                self._set_status(result.get('message', '已卸载'), ft.Colors.GREEN_400)
                self._append_terminal(f"uninstalled: {result.get('message')}")
                self._refresh_skills()
            else:
                self._set_status(f"卸载失败: {result.get('error', 'unknown')}", ft.Colors.RED_400)
        except Exception as e:
            self._append_terminal(f"uninstall error: {e}")
            self._set_status("Skill 卸载异常", ft.Colors.RED_400)

    def _install_skill_from_ui(self):
        name = self.skill_install_field.value.strip() if hasattr(self, 'skill_install_field') else ""
        if not name:
            self._set_status("请输入 Skill 名称或本地路径", ft.Colors.RED_400)
            return
        self._append_terminal(f"install skill: {name}")
        try:
            from prism.skills import skills
            result = skills.install_skill(name)
            if result.get('success'):
                self._set_status(result.get('message', '安装成功'), ft.Colors.GREEN_400)
                self._append_terminal(f"installed: {result.get('message')}")
                self.skill_install_field.value = ""
                if hasattr(self, 'skill_install_field') and self.skill_install_field:
                    self.skill_install_field.update()
                self._refresh_skills()
            else:
                self._set_status(f"安装失败: {result.get('error', 'unknown')}", ft.Colors.RED_400)
        except Exception as e:
            self._append_terminal(f"install error: {e}")
            self._set_status("Skill 安装异常", ft.Colors.RED_400)

    def _set_status(self, text: str, color=ft.Colors.GREEN_400):
        try:
            if not hasattr(self, "status_text") or self.status_text is None:
                return
            try:
                page = self.status_text.page
            except RuntimeError:
                return
            if page is None:
                return
            try:
                self.status_text.value = text
                self.status_text.color = color
                self.status_text.update()
            except Exception:
                try:
                    self.status_text.value = text
                    self.status_text.color = color
                    page.update([self.status_text])
                except Exception as exc:
                    logger.debug("status fallback update failed: %s", exc)
        except Exception:
            logger.debug('desktop exception: %s', traceback.format_exc())

    def _save_config(self):
        prism_config.set("model.default", self.model_dropdown.value)
        prism_config.set("model.provider", self.provider_textfield.value)
        prism_config.set("model.base_url", (self.base_url_textfield.value or "").strip())
        prism_config.set("model.api_key", self.api_key_textfield.value)
        self._set_status("配置已保存")
        self._append_terminal("配置已保存")
        try:
            self.agent = create_agent(enable_auto_memory=True)
        except Exception as exc:
            self.agent = None
            self._log_error("agent init", exc)
            self._append_terminal(f"agent recreate failed: {exc}")

    def _stop_send(self):
        self._generating = False
        self.stop_btn.visible = False
        self.send_btn.visible = True
        self.stop_btn.update()
        self.send_btn.update()
        self._set_status("已停止", ft.Colors.AMBER_400)
        try:
            self._log_to_file("info", "stream_stopped", chunks=getattr(self, "_chunk_count", 0))
        except Exception:
            logger.debug('desktop exception: %s', traceback.format_exc())


    def _check_browser_dependencies(self) -> dict:
        status = {"playwright": False, "chromium": False, "error": ""}
        try:
            import playwright
            status["playwright"] = True
        except Exception as e:
            status["error"] = f"playwright 未安装: {e}"
            return status
        try:
            from playwright.sync_api import sync_playwright
            with sync_playwright() as p:
                browser = p.chromium.launch(headless=True)
                version = browser.version
                browser.close()
                status["chromium"] = True
                status["version"] = version
        except Exception as e:
            status["chromium"] = False
            status["error"] = f"chromium 不可用: {e}"
        return status

    def _start_perf_monitor(self) -> None:
        try:
            import time, psutil
            from collections import deque
            self._perf_samples = deque(maxlen=30)
            self._perf_last_ts = time.perf_counter()
            self._perf_frames = 0
            self._perf_proc = psutil.Process()
            self._perf_log_counter = 0
        except Exception:
            logger.debug('desktop exception: %s', traceback.format_exc())

    def _perf_tick(self) -> None:
        try:
            import time
            self._perf_frames += 1
            now = time.perf_counter()
            dt = now - (self._perf_last_ts or now)
            if dt >= 1.0:
                fps = self._perf_frames / dt
                mem = self._perf_proc.memory_info().rss / (1024 * 1024)
                self._perf_samples.append((fps, mem))
                self._perf_frames = 0
                self._perf_last_ts = now
                self.perf_text.value = f"FPS:{fps:.0f} | MEM:{mem:.0f}MB"
                self.perf_text.update()
                self._perf_log_counter += 1
                if self._perf_log_counter % 5 == 0:
                    try:
                        self._log_to_file("debug", "perf_tick", fps=round(fps, 1), mem_mb=round(mem, 1))
                    except Exception:
                        logger.debug('desktop exception: %s', traceback.format_exc())
        except Exception:
            logger.debug('desktop exception: %s', traceback.format_exc())

    def _set_browser_status(self, connected: bool, title: str = ""):
        self.browser_connected = connected
        if connected:
            self.browser_status_icon.icon = ft.Icons.LANGUAGE_ROUNDED
            self.browser_status_icon.color = ft.Colors.GREEN_400
            self.browser_status_text.value = title or "已连接"
            self.browser_status_text.color = ft.Colors.GREEN_400
        else:
            self.browser_status_icon.icon = ft.Icons.LANGUAGE_ROUNDED
            self.browser_status_icon.color = ft.Colors.ON_SURFACE_VARIANT
            self.browser_status_text.value = "就绪"
            self.browser_status_text.color = ft.Colors.ON_SURFACE_VARIANT
        self.browser_status_icon.update()
        self.browser_status_text.update()

    def _run_terminal_command(self):
        command = self.terminal_input.value.strip() if hasattr(self, 'terminal_input') else ""
        if not command:
            return
        # Save to terminal history
        try:
            if not hasattr(self, "_terminal_history"):
                self._terminal_history = []
                self._terminal_history_index = -1
            if command and (not self._terminal_history or self._terminal_history[-1] != command):
                self._terminal_history.append(command)
                if len(self._terminal_history) > 200:
                    self._terminal_history = self._terminal_history[-200:]
            self._terminal_history_index = len(self._terminal_history)
        except Exception:
            logger.debug('desktop exception: %s', traceback.format_exc())
        self._append_terminal(f"$ {command}")
        self.terminal_input.value = ""
        self.terminal_input.update()
        try:
            import subprocess
            result = subprocess.run(command, shell=True, capture_output=True, text=True, timeout=30)
            output = result.stdout or result.stderr or '(no output)'
            self._append_terminal(output)
            self._append_mcp(f"[terminal] {command[:80]}")
        except Exception as e:
            self._append_terminal(f"终端执行失败：{e}")
        self._set_status("就绪")


def _start_voice_input(self):
    if not hasattr(self, "voice_record_btn") or self.voice_record_btn is None:
        return
    self._set_status("正在录音...", ft.Colors.AMBER_400)
    self._append_terminal("[voice] start recording")

    def _bg():
        try:
            from prism.voice import VoiceInteraction
            vi = VoiceInteraction()
            text = vi.listen()
            if not text:
                self._set_status("未识别到语音", ft.Colors.RED_400)
                return
            if hasattr(self, "input_field") and self.input_field is not None:
                self.input_field.value = text
                if hasattr(self.input_field, "update"):
                    self.input_field.update()
            self._set_status("语音转写完成", ft.Colors.GREEN_400)
            self._append_terminal(f"[voice] recognized: {text[:120]}")
        except Exception as exc:
            self._set_status("语音输入失败", ft.Colors.RED_400)
            self._append_terminal(f"[voice] error: {exc}")

    try:
        threading.Thread(target=_bg, daemon=True).start()
    except Exception as exc:
        self._set_status("语音线程启动失败", ft.Colors.RED_400)
        self._append_terminal(f"[voice] thread error: {exc}")


def _speak_last_reply(self):
    if not hasattr(self, "voice_speak_btn") or self.voice_speak_btn is None:
        return
    last = getattr(self, "_last_assistant_reply", "") or ""
    if not last.strip():
        self._set_status("没有可播报的内容", ft.Colors.RED_400)
        return
    self._set_status("正在播报...", ft.Colors.AMBER_400)
    self._append_terminal("[voice] tts start")

    def _bg():
        try:
            from prism.voice import VoiceInteraction
            vi = VoiceInteraction()
            vi.speak(last)
            self._set_status("播报完成", ft.Colors.GREEN_400)
            self._append_terminal("[voice] tts done")
        except Exception as exc:
            self._set_status("语音播报失败", ft.Colors.RED_400)
            self._append_terminal(f"[voice] tts error: {exc}")

    try:
        threading.Thread(target=_bg, daemon=True).start()
    except Exception as exc:
        self._set_status("语音线程启动失败", ft.Colors.RED_400)
        self._append_terminal(f"[voice] thread error: {exc}")


def _refresh_workflows(self):
    if not hasattr(self, "workflow_list") or self.workflow_list is None:
        return
    self._append_terminal("refresh workflows ...")
    try:
        from prism.workflow import list_workflows
        items = list_workflows()
        self._workflow_items = items
        self._render_workflow_items(items)
        self._append_terminal(f"workflows refreshed: {len(items)} 个")
    except Exception as exc:
        self._append_terminal(f"workflow error: {exc}")
        self._set_status("工作流刷新失败", ft.Colors.RED_400)


def _render_workflow_items(self, items):
    if not hasattr(self, "workflow_list") or self.workflow_list is None:
        return
    self.workflow_list.controls.clear()
    if not items:
        self.workflow_list.controls.append(ft.Container(
            content=ft.Column([
                ft.Icon(ft.Icons.ACCOUNT_TREE_OFF_ROUNDED, size=28, color=ft.Colors.ON_SURFACE_VARIANT, opacity=0.5),
                ft.Text("暂无工作流", size=12, color=ft.Colors.ON_SURFACE_VARIANT, opacity=0.95),
            ], alignment=ft.MainAxisAlignment.CENTER, horizontal_alignment=ft.CrossAxisAlignment.CENTER, tight=True),
            padding=ft.Padding(48, 48, 48, 48),
            border_radius=12,
            bgcolor=ft.Colors.with_opacity(0.6, ft.Colors.SURFACE_CONTAINER),
        ))
    else:
        for item in items:
            steps = item.get("steps", [])
            step_count = len(steps) if isinstance(steps, list) else 0
            row = ft.Row([
                ft.Column([
                    ft.Text(item.get("name", "unknown"), size=12, weight=ft.FontWeight.W_500, color=ft.Colors.ON_SURFACE),
                    ft.Text(f"{step_count} 步骤 · {item.get('description', '')}", size=10, color=ft.Colors.ON_SURFACE_VARIANT, opacity=0.85, max_lines=1, overflow=ft.TextOverflow.ELLIPSIS),
                ], spacing=2, expand=True),
                ft.TextButton("运行", style=ft.ButtonStyle(shape=ft.RoundedRectangleBorder(radius=12), bgcolor=ft.Colors.PRIMARY_CONTAINER, color=ft.Colors.ON_PRIMARY_CONTAINER), on_click=lambda e, n=item.get("name"): self._run_workflow_from_ui(n)),
            ], spacing=8, tight=True)
            self.workflow_list.controls.append(row)
    self.workflow_list.update()


def _run_workflow_from_ui(self, name: str):
    if not name:
        return
    self._append_terminal(f"run workflow: {name}")
    self._set_status(f"执行工作流: {name}", ft.Colors.AMBER_400)
    try:
        from prism.workflow import run_workflow
        result = run_workflow(name, parent_agent=getattr(self, "agent", None))
        if result.get("success"):
            output = result.get("result", "")
            if hasattr(self, "agent") and self.agent is not None:
                self._append("PRISM", output)
            self._set_status("工作流完成", ft.Colors.GREEN_400)
            self._append_terminal(f"workflow done: {name}")
        else:
            self._set_status(f"工作流失败: {result.get('error', 'unknown')}", ft.Colors.RED_400)
    except Exception as exc:
        self._set_status("工作流执行异常", ft.Colors.RED_400)
        self._append_terminal(f"workflow run error: {exc}")


def _refresh_usage_dash(self):
    try:
        from prism.usage import usage_tracker
        s = usage_tracker.stats()
        if hasattr(self, "usage_calls_text") and self.usage_calls_text:
            self.usage_calls_text.value = str(s.get("total_calls", 0))
            self.usage_success_text.value = f"{s.get('success_rate', 0.0)}%"
            self.usage_latency_text.value = f"{s.get('avg_latency_ms', 0.0)}ms"
            self.usage_tokens_text.value = str(int(s.get("total_prompt_tokens", 0)) + int(s.get("total_completion_tokens", 0)))
            self.usage_cost_text.value = f"${s.get('total_cost_usd', 0.0)}"
            self.usage_calls_text.update()
            self.usage_success_text.update()
            self.usage_latency_text.update()
            self.usage_tokens_text.update()
            self.usage_cost_text.update()
    except Exception as exc:
        self._append_terminal(f"usage dash error: {exc}")


def _apply_persona(self, name: str):
    try:
        from prism.personas import persona_manager
        persona = persona_manager.activate(name)
        if not persona:
            self._set_status(f"角色不存在: {name}", ft.Colors.RED_400)
            return
        self._set_status(f"已切换角色: {persona.name}", ft.Colors.GREEN_400)
        if getattr(self, "agent", None) and persona.system_prompt:
            self.agent.system_prompt = persona.system_prompt
    except Exception as exc:
        self._set_status("角色切换失败", ft.Colors.RED_400)
        self._append_terminal(f"persona error: {exc}")


def main():
    def _app(page: ft.Page):
        PrismDesktop(page)
    ft.run(main=_app)


if __name__ == "__main__":
    main()