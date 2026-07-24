"""
PRISM Agent - MCP 服务器配置加载
支持从 YAML/JSON 加载 MCP 服务器配置
"""

import json
import os
from pathlib import Path
from typing import Dict, Any, List, Optional

from prism.logging import logger
import traceback
from prism.paths import PRISM_HOME


class MCPConfigError(Exception):
    """MCP 配置校验错误"""


def _validate_mcp_config(name: str, cfg: Dict[str, Any]) -> List[str]:
    """校验单个服务器配置，返回错误列表"""
    errors: List[str] = []
    transport = (cfg.get("transport") or "stdio").strip().lower()
    if transport not in ("stdio", "http", "sse"):
        errors.append(f"{name}: transport 必须为 stdio/http/sse")
    if transport == "stdio":
        if not cfg.get("command"):
            errors.append(f"{name}: stdio 模式必须提供 command")
    elif transport in ("http", "sse"):
        if not cfg.get("url"):
            errors.append(f"{name}: {transport} 模式必须提供 url")
    timeout = cfg.get("timeout")
    if timeout is not None:
        try:
            t = int(timeout)
            if t <= 0:
                errors.append(f"{name}: timeout 必须为正整数")
        except (TypeError, ValueError):
            errors.append(f"{name}: timeout 必须为整数")
    retries = cfg.get("retries")
    if retries is not None:
        try:
            r = int(retries)
            if r < 0:
                errors.append(f"{name}: retries 不能为负数")
        except (TypeError, ValueError):
            errors.append(f"{name}: retries 必须为整数")
    return errors


def validate_mcp_config(data: Dict[str, Any]) -> Dict[str, List[str]]:
    """校验完整 MCP 配置，返回 {server_name: [errors]}"""
    result: Dict[str, List[str]] = {}
    for name, cfg in data.items():
        errors = _validate_mcp_config(name, cfg)
        if errors:
            result[name] = errors
    return result


def load_mcp_config(config_path: Optional[str] = None) -> List[Any]:
    """
    加载 MCP 服务器配置
    
    Args:
        config_path: 配置文件路径，默认 ~/.prism/mcp.json
    
    Returns:
        MCPServer 列表
    """
    from prism.mcp import MCPServer
    
    if not config_path:
        config_path = str(PRISM_HOME / "mcp.json")
    
    path = Path(config_path)
    if not path.exists():
        return []
    
    try:
        with open(path, 'r', encoding='utf-8') as f:
            data = json.load(f)
    except Exception as e:
        logger.debug("load mcp config failed: %s", traceback.format_exc())
        logger.debug("[MCP] 加载配置失败: {e}")
        return []
    
    validation = validate_mcp_config(data)
    for name, errors in validation.items():
        for error in errors:
            logger.debug("[MCP] 配置错误: {error}")
    
    servers = []
    for name, cfg in data.items():
        if name in validation and cfg.get("enabled", True):
            logger.debug("[MCP] 跳过无效服务器: {name}")
            continue
        server = MCPServer(
            name=name,
            transport=cfg.get("transport", "stdio"),
            command=cfg.get("command"),
            url=cfg.get("url"),
            args=cfg.get("args", []),
            env=cfg.get("env"),
            enabled=cfg.get("enabled", True),
            timeout=int(cfg.get("timeout") or 30),
            retries=int(cfg.get("retries") or 2),
            tool_timeouts=cfg.get("tool_timeouts"),
        )
        servers.append(server)
    
    return servers


def setup_mcp_servers(config_path: Optional[str] = None):
    """
    设置 MCP 服务器
    
    Args:
        config_path: 配置文件路径
    """
    from prism.mcp import mcp_client
    
    servers = load_mcp_config(config_path)
    
    for server in servers:
        if server.enabled:
            mcp_client.add_server(server)
            logger.debug("[MCP] 已添加服务器: {server.name} ({server.transport})")
    
    return mcp_client


def create_default_mcp_config() -> str:
    """创建默认 MCP 配置文件"""
    config_dir = PRISM_HOME
    config_dir.mkdir(parents=True, exist_ok=True)
    
    config_path = config_dir / "mcp.json"
    
    default_config = {
        "filesystem": {
            "transport": "stdio",
            "command": "npx",
            "args": ["-y", "@modelcontextprotocol/server-filesystem", str(config_dir)],
            "enabled": True,
            "timeout": 30,
            "retries": 2,
        },
        "github": {
            "transport": "stdio",
            "command": "npx",
            "args": ["-y", "@modelcontextprotocol/server-github"],
            "enabled": False,
            "timeout": 30,
            "retries": 2,
        },
        "example-http": {
            "transport": "http",
            "url": "http://localhost:3000/mcp",
            "enabled": False,
            "timeout": 15,
            "retries": 3,
        },
    }
    
    with open(config_path, 'w', encoding='utf-8') as f:
        json.dump(default_config, f, indent=2, ensure_ascii=False)
    
    logger.debug("[MCP] 默认配置已创建: {config_path}")
    return str(config_path)
