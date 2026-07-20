"""
PRISM Agent - Gateway 自配置工具
让 Agent 在对话里直接配置/启停 gateway。
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
from typing import Any, Dict, Optional

from prism.logging import logger

try:
    from prism.tools.registry import registry, Tool
except Exception:
    class Tool:  # type: ignore[no-redef]
        pass


class GatewaySetupTool(Tool):
    name = "gateway_setup"
    description = "配置 gateway 平台；支持平台：feishu/telegram/wechat"
    input_schema = {
        "type": "object",
        "properties": {
            "platform": {"type": "string", "description": "平台名称，如 feishu"},
            "app_id": {"type": "string", "description": "飞书 App ID"},
            "app_secret": {"type": "string", "description": "飞书 App Secret"},
            "token": {"type": "string", "description": "Telegram Bot Token / 企业微信 CorpSecret"},
            "encrypt_key": {"type": "string", "description": "飞书 Encrypt Key"},
            "verification_token": {"type": "string", "description": "飞书 Verification Token"},
        },
        "required": ["platform"],
    }

    def execute(self, **kwargs) -> Dict[str, Any]:
        platform = kwargs.get("platform")
        if not platform:
            return {"success": False, "error": "缺少 platform"}
        try:
            from prism.cli.gateway import (
                _resolve_config_path,
                _load_config,
                setup_gateway_platform,
            )
        except Exception as e:
            return {"success": False, "error": f"导入 gateway CLI 失败: {e}"}

        try:
            cfg_path = _resolve_config_path()
            cfg = _load_config(cfg_path)
            setup_gateway_platform(cfg, platform, kwargs)
            with open(cfg_path, "w", encoding="utf-8") as f:
                import yaml

                yaml.dump(cfg, f, allow_unicode=True, default_flow_style=False)
            return {"success": True, "path": str(cfg_path), "platform": platform}
        except Exception as e:
            logger.debug("gateway_setup failed: %s", __import__("traceback").format_exc())
            return {"success": False, "error": str(e)}


class GatewayStartTool(Tool):
    name = "gateway_start"
    description = "启动 gateway；支持 --platform feishu/telegram/wechat"
    input_schema = {
        "type": "object",
        "properties": {
            "platform": {"type": "string", "description": "要启动的平台"},
        },
        "required": ["platform"],
    }

    def execute(self, **kwargs) -> Dict[str, Any]:
        platform = kwargs.get("platform")
        if not platform:
            return {"success": False, "error": "缺少 platform"}

        cmd = [
            sys.executable,
            "-m",
            "prism.cli",
            "gateway",
            "start",
            "--platform",
            platform,
        ]
        try:
            proc = subprocess.Popen(
                cmd,
                cwd=os.path.dirname(sys.executable),
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
            )
            return {
                "success": True,
                "pid": proc.pid,
                "command": " ".join(cmd),
            }
        except Exception as e:
            return {"success": False, "error": str(e)}


class GatewayStatusTool(Tool):
    name = "gateway_status"
    description = "查看 gateway 运行状态与已配置平台"
    input_schema = {
        "type": "object",
        "properties": {},
        "required": [],
    }

    def execute(self, **kwargs) -> Dict[str, Any]:
        try:
            from prism.config import config as prism_config

            cfg = prism_config.get("gateway") or {}
            platforms = cfg.get("platforms") or []
            detail = {}
            for p in platforms:
                detail[p] = {
                    k: ("***" if "secret" in k.lower() or "token" in k.lower() else v)
                    for k, v in (cfg.get(p) or {}).items()
                }
            return {"success": True, "platforms": platforms, "detail": detail}
        except Exception as e:
            return {"success": False, "error": str(e)}


def register(reg: Any) -> None:
    try:
        reg.register(GatewaySetupTool())
        reg.register(GatewayStartTool())
        reg.register(GatewayStatusTool())
    except Exception as exc:
        logger.debug("register gateway tools failed: %s", exc)
