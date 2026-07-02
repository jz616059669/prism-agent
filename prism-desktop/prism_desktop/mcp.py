"""PRISM Desktop - MCP 面板逻辑"""
from __future__ import annotations

from typing import TYPE_CHECKING

import flet as ft
from prism_desktop.i18n import gettext as _

from prism.logging import logger
import traceback

from prism.config import config as prism_config

if TYPE_CHECKING:
    from prism_desktop.main import PrismDesktop


def _refresh_mcp(self: PrismDesktop):
    self._append_terminal("mcp refresh ...")
    self.mcp_server_list.controls.clear()
    try:
        raw = prism_config.get("mcp.servers") or []
    except Exception:
        logger.debug("mcp config get failed: %s", traceback.format_exc())
        raw = []
    if not raw:
        self.mcp_server_list.controls.append(
            ft.Text("未配置 MCP 服务器", size=12, color=ft.Colors.ON_SURFACE)
        )
    else:
        for idx, server in enumerate(raw):
            name = server.get("name") or server.get("id") or f"server_{idx+1}"
            transport = server.get("transport", "unknown")
            status = "未启动"
            start_btn = ft.TextButton("启动", data=name)
            start_btn.on_click = lambda e, s=name, b=start_btn: _toggle_mcp_server(self, s, b)
            log_btn = ft.TextButton("日志", data=name)
            log_btn.on_click = lambda e, s=name: _show_mcp_log(self, s)
            tools_btn = ft.TextButton("工具", data=name)
            tools_btn.on_click = lambda e, s=name: _show_mcp_tools(self, s)
            row = ft.Row(
                [
                    ft.Text(name, size=12, expand=True),
                    ft.Text(transport, size=10, color=ft.Colors.ON_SURFACE_VARIANT),
                    ft.Text(status, size=11, color=ft.Colors.ON_SURFACE),
                    start_btn,
                    tools_btn,
                    log_btn,
                ]
            )
            self.mcp_server_list.controls.append(row)
    self.mcp_server_list.update()
    self._append_mcp(f"已刷新 MCP 服务器：{len(raw)} 个")


def _toggle_mcp_server(self: PrismDesktop, name: str, button: ft.TextButton):
    self._append_terminal(f"mcp toggle {name}")
    try:
        from prism.mcp import mcp_client
        current = self._mcp_server_status.get(name, False)
        if current:
            mcp_client.close()
            self._mcp_server_status[name] = False
            state = "已停止"
            button.text = "启动"
        else:
            raw = prism_config.get("mcp.servers") or []
            server_cfg = next((s for s in raw if (s.get("name") or s.get("id")) == name), None)
            if server_cfg:
                from prism.mcp import MCPServer
                mcp_client.add_server(MCPServer(
                    name=name,
                    transport=server_cfg.get("transport", "stdio"),
                    command=server_cfg.get("command"),
                    url=server_cfg.get("url"),
                    args=server_cfg.get("args") or [],
                ))
                self._mcp_server_status[name] = True
                state = "已启动"
                button.text = "已启动"
            else:
                state = "配置缺失"
                button.text = "启动"
        self._append_mcp(f"[{name}] {state}")
        button.update()
    except Exception as e:
        self._append_mcp(f"[{name}] 切换失败：{e}")


def _show_mcp_log(self: PrismDesktop, name: str):
    self._append_mcp(f"[{name}] 日志入口后续接入真实 MCP 客户端")
    self._append_terminal(f"mcp log {name}")


def _show_mcp_tools(self: PrismDesktop, name: str):
    self._append_terminal(f"mcp tools {name}")
    try:
        from prism.mcp import mcp_client
        tools = mcp_client.list_tools(name)
        self.mcp_list.controls.clear()
        if not tools:
            self.mcp_list.controls.append(ft.Text("暂无工具", size=12, color=ft.Colors.ON_SURFACE))
        else:
            for tool in tools:
                schema = tool.get("inputSchema") or {}
                self.mcp_list.controls.append(
                    ft.Text(f"- {tool.get('name')}: {tool.get('description', '')}", size=11)
                )
        self.mcp_list.update()
        self._append_mcp(f"[{name}] 工具数：{len(tools)}")
    except Exception as e:
        self._append_mcp(f"[{name}] 工具获取失败：{e}")