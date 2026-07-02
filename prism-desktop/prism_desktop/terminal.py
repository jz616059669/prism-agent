"""PRISM Desktop - 终端与 MCP 面板逻辑"""
from __future__ import annotations

import subprocess
from typing import TYPE_CHECKING

import flet as ft

from prism.logging import logger
import traceback

if TYPE_CHECKING:
    from prism_desktop.main import PrismDesktop


class TerminalMixin:
    def _run_terminal_command(self):
        command = (self.terminal_input.value or "").strip()
        if not command:
            return
        self._append_terminal(f"$ {command}")
        self.terminal_input.value = ""
        self.terminal_input.update()
        try:
            result = subprocess.run(command, shell=True, capture_output=True, text=True, timeout=30)
            output = result.stdout or result.stderr or '(no output)'
            self._append_terminal(output)
            self._append_mcp(f"[terminal] {command[:80]}")
        except Exception as e:
            self._append_terminal(f"终端执行失败：{e}")
        self._set_status("就绪")

    def _append_terminal(self, text: str):
        if not hasattr(self, "_terminal_lines"):
            self._terminal_lines = []
        self._terminal_lines.append(text)
        if len(self._terminal_lines) > 300:
            self._terminal_lines = self._terminal_lines[-300:]
        if not hasattr(self, "terminal_list") or self.terminal_list is None:
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
        try:
            self.terminal_list.controls.append(ft.Text(text, size=12, color=color, selectable=True, font_family="Consolas, Monaco, monospace", height=18))
            self.terminal_list.update()
        except Exception:
            logger.debug("append terminal update failed: %s", traceback.format_exc())
            pass

    def _append_mcp(self, text: str):
        if not hasattr(self, "_mcp_logs"):
            self._mcp_logs = []
        self._mcp_logs.append(text)
        if len(self._mcp_logs) > 200:
            self._mcp_logs = self._mcp_logs[-200:]
        if not hasattr(self, "mcp_list") or self.mcp_list is None:
            return
        try:
            self.mcp_list.controls.clear()
            for line in self._mcp_logs[-80:]:
                self.mcp_list.controls.append(ft.Text(line, size=12, color=ft.Colors.ON_SURFACE, selectable=True, font_family="Consolas, Monaco, monospace", height=18))
            self.mcp_list.update()
        except Exception:
            logger.debug("append mcp update failed: %s", traceback.format_exc())
            pass

    def _clear_terminal(self):
        self._terminal_lines = []
        if hasattr(self, "terminal_list") and self.terminal_list is not None:
            try:
                self.terminal_list.controls.clear()
                self.terminal_list.update()
            except Exception:
                logger.debug("clear terminal failed: %s", traceback.format_exc())
                pass

    def _clear_mcp(self):
        self._mcp_logs = []
        if hasattr(self, "mcp_list") and self.mcp_list is not None:
            try:
                self.mcp_list.controls.clear()
                self.mcp_list.update()
            except Exception:
                logger.debug("clear mcp failed: %s", traceback.format_exc())
                pass
