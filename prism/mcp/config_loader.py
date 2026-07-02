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


def _load_mcp_module():
    """延迟导入 prism.mcp，避免模块结构变化时顶层 ImportError。"""
    from prism.mcp import MCPServer, mcp_client
    return MCPServer, mcp_client


def load_mcp_config(config_path: Optional[str] = None) -> List[Any]:
    """
    加载 MCP 服务器配置
    
    Args:
        config_path: 配置文件路径，默认 ~/.prism/mcp.json
    
    Returns:
        MCPServer 列表
    """
    MCPServer, _ = _load_mcp_module()
    
    if not config_path:
        config_path = str(PRISM_HOME / "mcp.json")
    
    path = Path(config_path)
    if not path.exists():
        return []
    
    try:
        with open(path, 'r', encoding='utf-8') as f:
            data = json.load(f)
        
        servers = []
        for name, cfg in data.items():
            server = MCPServer(
                name=name,
                transport=cfg.get("transport", "stdio"),
                command=cfg.get("command"),
                url=cfg.get("url"),
                args=cfg.get("args", []),
                enabled=cfg.get("enabled", True),
            )
            servers.append(server)
        
        return servers
    except Exception as e:
        logger.debug("load mcp config failed: %s", traceback.format_exc())
        print(f"[MCP] 加载配置失败: {e}")
        return []


def setup_mcp_servers(config_path: Optional[str] = None):
    """
    设置 MCP 服务器
    
    Args:
        config_path: 配置文件路径
    """
    _, mcp_client = _load_mcp_module()
    
    servers = load_mcp_config(config_path)
    
    for server in servers:
        if server.enabled:
            mcp_client.add_server(server)
            print(f"[MCP] 已添加服务器: {server.name} ({server.transport})")
    
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
        },
        "github": {
            "transport": "stdio",
            "command": "npx",
            "args": ["-y", "@modelcontextprotocol/server-github"],
            "enabled": False,
        }
    }
    
    with open(config_path, 'w', encoding='utf-8') as f:
        json.dump(default_config, f, indent=2, ensure_ascii=False)
    
    print(f"[MCP] 默认配置已创建: {config_path}")
    return str(config_path)
