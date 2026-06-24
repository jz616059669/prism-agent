"""
PRISM Agent - 统一工具系统
整合文件操作、终端执行、浏览器自动化、代码执行
"""

import json
import os
import subprocess
import tempfile
from typing import Dict, List, Any, Optional, Callable
from abc import ABC, abstractmethod
from pathlib import Path


class Tool(ABC):
    """工具基类"""
    
    @property
    @abstractmethod
    def name(self) -> str:
        pass
    
    @property
    @abstractmethod
    def description(self) -> str:
        pass
    
    @abstractmethod
    def execute(self, **kwargs) -> Dict[str, Any]:
        pass


class FileReadTool(Tool):
    """文件读取工具"""
    
    name = "file_read"
    description = "读取文件内容，支持offset/limit分页"
    
    def execute(self, path: str, offset: int = 1, limit: int = 500) -> Dict[str, Any]:
        try:
            with open(path, 'r', encoding='utf-8') as f:
                lines = f.readlines()
            total = len(lines)
            start = max(0, offset - 1)
            end = min(total, start + limit)
            content = ''.join(lines[start:end])
            return {
                'success': True,
                'content': content,
                'total_lines': total,
                'offset': offset,
                'limit': limit,
            }
        except Exception as e:
            return {'success': False, 'error': str(e)}


class FileWriteTool(Tool):
    """文件写入工具"""
    
    name = "file_write"
    description = "写入文件内容，自动创建父目录"
    
    def execute(self, path: str, content: str) -> Dict[str, Any]:
        try:
            Path(path).parent.mkdir(parents=True, exist_ok=True)
            with open(path, 'w', encoding='utf-8') as f:
                f.write(content)
            return {'success': True, 'path': path}
        except Exception as e:
            return {'success': False, 'error': str(e)}


class FilePatchTool(Tool):
    """文件补丁工具"""
    
    name = "file_patch"
    description = "对文件进行精确替换，支持replace/patch模式"
    
    def execute(self, path: str, old_string: str, new_string: str, 
                mode: str = 'replace', replace_all: bool = False) -> Dict[str, Any]:
        try:
            with open(path, 'r', encoding='utf-8') as f:
                content = f.read()
            
            if mode == 'replace':
                if old_string not in content:
                    return {'success': False, 'error': 'old_string not found'}
                
                if replace_all:
                    new_content = content.replace(old_string, new_string)
                else:
                    new_content = content.replace(old_string, new_string, 1)
            else:
                return {'success': False, 'error': 'patch mode not implemented yet'}
            
            with open(path, 'w', encoding='utf-8') as f:
                f.write(new_content)
            
            return {'success': True, 'path': path}
        except Exception as e:
            return {'success': False, 'error': str(e)}


class TerminalTool(Tool):
    """终端执行工具"""
    
    name = "terminal"
    description = "执行shell命令，支持background/pty/timeout"
    
    def execute(self, command: str, timeout: int = 180, 
                background: bool = False, workdir: Optional[str] = None) -> Dict[str, Any]:
        try:
            cwd = workdir or os.getcwd()
            result = subprocess.run(
                command,
                shell=True,
                capture_output=True,
                text=True,
                timeout=timeout,
                cwd=cwd,
                env={**os.environ, 'PYTHONIOENCODING': 'utf-8'},
            )
            return {
                'success': result.returncode == 0,
                'output': result.stdout,
                'error': result.stderr,
                'exit_code': result.returncode,
            }
        except subprocess.TimeoutExpired:
            return {'success': False, 'error': f'Command timed out after {timeout}s'}
        except Exception as e:
            return {'success': False, 'error': str(e)}


class ToolRegistry:
    """工具注册表 - 统一管理所有工具"""
    
    def __init__(self):
        self._tools: Dict[str, Tool] = {}
        self._register_defaults()
    
    def _register_defaults(self):
        """注册默认工具"""
        self.register(FileReadTool())
        self.register(FileWriteTool())
        self.register(FilePatchTool())
        self.register(TerminalTool())
    
    def register(self, tool: Tool):
        """注册工具"""
        self._tools[tool.name] = tool
    
    def get(self, name: str) -> Optional[Tool]:
        """获取工具"""
        return self._tools.get(name)
    
    def list_tools(self) -> List[Dict[str, str]]:
        """列出所有工具"""
        return [
            {'name': t.name, 'description': t.description}
            for t in self._tools.values()
        ]
    
    def execute(self, name: str, **kwargs) -> Dict[str, Any]:
        """执行工具"""
        tool = self._tools.get(name)
        if not tool:
            return {'success': False, 'error': f'Tool not found: {name}'}
        return tool.execute(**kwargs)


# 全局工具注册表
registry = ToolRegistry()
