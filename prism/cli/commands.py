"""PRISM Agent - CLI Commands"""
from __future__ import annotations

import sys
import os
from pathlib import Path
from typing import Optional

import click
import logging
import traceback

from prism.logging import logger
from rich.console import Console
from rich.panel import Panel
from rich.markdown import Markdown
from rich.syntax import Syntax
from rich.prompt import Prompt

from prism.config import config as prism_config
from prism.config import ConfigError
from prism.agent import create_agent

console = Console()


def show_help():
    """显示帮助信息"""
    help_text = """
**可用命令：**
- `/help` - 显示帮助
- `/exit` - 退出
- `/tools` - 列出所有工具
- `/model` - 显示当前模型
- `/clear` - 清空对话历史

**示例：**
- "帮我写一个Python脚本"
- "读取文件 README.md"
- "执行命令 ls -la"
- "搜索网页 Python教程"
    """
    console.print(Markdown(help_text))


def show_tools(agent):
    """显示可用工具"""
    tools = agent.list_tools()
    console.print("\n[bold cyan]可用工具：[/bold cyan]")
    for tool in tools:
        console.print(f"  • [green]{tool['name']}[/green]: {tool['description']}")
    console.print()


def show_model():
    """显示模型配置"""
    model = prism_config.get('model.default', 'step-3.7-flash')
    provider = prism_config.get('model.provider', 'openai')
    base_url = prism_config.get('model.base_url', '')
    
    console.print(f"\n[bold cyan]当前模型配置：[/bold cyan]")
    console.print(f"  模型: [green]{model}[/green]")
    console.print(f"  提供商: [green]{provider}[/green]")
    console.print(f"  API地址: [green]{base_url}[/green]\n")
