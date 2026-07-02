"""PRISM Desktop - 系统托盘、关于、配置目录、终端打开等系统逻辑"""
from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path
from typing import TYPE_CHECKING

import flet as ft

from prism.logging import logger
import traceback

if TYPE_CHECKING:
    from prism_desktop.main import PrismDesktop


class SystemMixin:
    def _bind_tray(self) -> None:
        tray_dir = Path(__file__).parent
        icons = {
            "default": str(tray_dir / "icon.png"),
            "connected": str(tray_dir / "icon.png"),
        }
        icon_path = icons.get("default")
        if not Path(icon_path).exists():
            icon_path = None

        def _on_tray_click(icon, item):
            try:
                self.page.set_window_state("normal")
                self.page.bring_to_front()
            except Exception:
                logger.debug("tray click failed: %s", traceback.format_exc())

        def _on_exit(icon, item):
            try:
                self.page.window_close()
            except Exception:
                logger.debug("desktop exception: %s", traceback.format_exc())
                pass
            try:
                self.page.window_destroy()
            except Exception:
                logger.debug("desktop exception: %s", traceback.format_exc())
                pass
            try:
                if sys.platform == "win32":
                    os._exit(0)
                else:
                    raise SystemExit
            except Exception:
                logger.debug("desktop exception: %s", traceback.format_exc())
                pass

        try:
            import pystray
            image = None
            if icon_path:
                try:
                    from PIL import ImageGrab
                    image = ImageGrab.grab()
                except Exception:
                    logger.debug("tray icon ImageGrab failed: %s", traceback.format_exc())
                    try:
                        from PIL import Image
                        image = Image.new("RGB", (64, 64), color=(73, 109, 137))
                    except Exception:
                        logger.debug("tray icon Image.new failed: %s", traceback.format_exc())
                        image = None
            if image is not None:
                menu = pystray.Menu(
                    pystray.MenuItem("显示窗口", _on_tray_click),
                    pystray.MenuItem("退出", _on_exit),
                )
                self._tray_icon = pystray.Icon("prism", image, "PRISM", menu)
                self._tray_icon.run_detached()
        except Exception as e:
            print(f"tray init skipped: {e}")

    def _bind_context_menu(self) -> None:
        return

    def _minimize_to_tray(self) -> None:
        try:
            self.page.set_window_state("minimized")
        except Exception:
            logger.debug("desktop exception: %s", traceback.format_exc())
            pass
        self._append_terminal("minimize to tray")

    def _open_config_dir(self, e):
        config_dir = Path.home() / ".prism"
        config_dir.mkdir(parents=True, exist_ok=True)
        try:
            if sys.platform == "win32":
                os.startfile(str(config_dir))
            elif sys.platform == "darwin":
                subprocess.run(["open", str(config_dir)], check=False)
            else:
                subprocess.run(["xdg-open", str(config_dir)], check=False)
        except Exception as ex:
            self._append_terminal(f"open config dir failed: {ex}")
        self._append_terminal(f"open config dir: {config_dir}")

    def _open_terminal_here(self, e):
        try:
            if sys.platform == "win32":
                subprocess.run(["cmd", "/c", "start", "cmd"], shell=False, check=False)
            elif sys.platform == "darwin":
                subprocess.run(["open", "-a", "Terminal", "."], check=False)
            else:
                subprocess.run(["xdg-terminal-exec", "."], check=False)
        except Exception as ex:
            self._append_terminal(f"open terminal failed: {ex}")
        self._append_terminal("open terminal")

    def _about(self, e):
        config_path = str(Path.home() / ".prism")
        content = ft.Column(
            [
                ft.Text("PRISM Agent", size=20, weight=ft.FontWeight.BOLD),
                ft.Divider(height=12),
                ft.Text("版本：2.1.1", size=14),
                ft.Text("配置目录：", size=12, weight=ft.FontWeight.BOLD),
                ft.Text(config_path, size=11, color=ft.Colors.ON_SURFACE_VARIANT),
                ft.TextButton("打开配置目录", on_click=lambda ev: self._open_config_dir(ev)),
                ft.Container(height=8),
                ft.Text("模型配置", size=12, weight=ft.FontWeight.BOLD),
                ft.Text(f"提供商：{getattr(self, 'provider_textfield', None) and self.provider_textfield.value or '-'}", size=11),
                ft.Text(f"模型：{getattr(self, 'model_dropdown', None) and self.model_dropdown.value or '-'}", size=11),
                ft.Text(f"Base URL：{(getattr(self, 'base_url_textfield', None) and self.base_url_textfield.value or '-')[:60]}", size=11),
            ],
            tight=True,
            width=360,
        )
        self.page.dialog = ft.AlertDialog(
            title=ft.Text("关于 PRISM Agent"),
            content=content,
            actions=[
                ft.TextButton("前往 GitHub 检查更新", on_click=lambda ev: self._open_github_releases(ev)),
                ft.TextButton("关闭", on_click=lambda ev: self.page.close_dialog()),
            ],
        )
        self.page.dialog.open = True
        self.page.update()
        self._append_terminal("about dialog opened")

    def _open_github_releases(self, e):
        try:
            url = "https://github.com/jz616059669/prism-agent/releases/latest"
            if sys.platform == "win32":
                os.startfile(url)
            elif sys.platform == "darwin":
                subprocess.run(["open", url], check=False)
            else:
                subprocess.run(["xdg-open", url], check=False)
            self._append_terminal("open github releases")
        except Exception as ex:
            self._append_terminal(f"open github releases failed: {ex}")
