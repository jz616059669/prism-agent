"""
PRISM Agent - 统一工具系统
整合文件操作、终端执行、浏览器自动化、代码执行
"""

import json
import logging
import os
import re
import shlex
import subprocess
import tempfile
import traceback
from typing import Dict, List, Any, Optional

from prism.interfaces import Tool

logger = logging.getLogger("prism.tools")

# 延迟导入浏览器模块，避免强依赖
try:
    from prism.tools.browser import browser as browser_api
    BROWSER_AVAILABLE = True
except Exception:
    BROWSER_AVAILABLE = False
    logger.debug("browser tool import failed: %s", traceback.format_exc())

# 延迟导入代码执行器
try:
    from prism.tools.code_executor import CodeExecutor

    CODE_EXECUTOR_AVAILABLE = True
    _code_executor = CodeExecutor()
except Exception:
    CODE_EXECUTOR_AVAILABLE = False
    _code_executor = None
    logger.debug("code executor import failed: %s", traceback.format_exc())


class FileReadTool(Tool):
    """文件读取工具"""
    
    name = "file_read"
    description = "读取文件内容，支持offset/limit分页"
    input_schema = {
        "type": "object",
        "properties": {
            "path": {"type": "string", "description": "文件路径"},
            "offset": {"type": "integer", "description": "起始行号，从1开始", "default": 1},
            "limit": {"type": "integer", "description": "最大读取行数", "default": 500},
        },
        "required": ["path"],
    }
    
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
    input_schema = {
        "type": "object",
        "properties": {
            "path": {"type": "string", "description": "文件路径"},
            "content": {"type": "string", "description": "文件内容"},
        },
        "required": ["path", "content"],
    }
    
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
    input_schema = {
        "type": "object",
        "properties": {
            "path": {"type": "string", "description": "文件路径"},
            "old_string": {"type": "string", "description": "旧文本"},
            "new_string": {"type": "string", "description": "新文本"},
            "mode": {"type": "string", "description": "replace 或 patch", "default": "replace"},
            "replace_all": {"type": "boolean", "description": "是否全部替换", "default": False},
        },
        "required": ["path", "old_string", "new_string"],
    }
    
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
    description = "执行 shell 命令，返回 stdout/stderr/exit_code"
    input_schema = {
        "type": "object",
        "properties": {
            "command": {"type": "string", "description": "要执行的命令"},
            "timeout": {"type": "integer", "description": "超时秒数", "default": 180},
            "workdir": {"type": "string", "description": "工作目录"},
        },
        "required": ["command"],
    }
    
    def execute(self, command: str, timeout: int = 180, workdir: Optional[str] = None) -> Dict[str, Any]:
        if not command or not command.strip():
            return {'success': False, 'error': 'Empty command'}
        if len(command) > 4096:
            return {'success': False, 'error': 'Command too long (max 4096 chars)', 'exit_code': -1}

        # 安全检查：禁止明显危险的命令模式
        dangerous_patterns = [
            r'rm\s+-rf\s+/',
            r'del\s+/[fs]',
            r'format\s+[c-z]:',
            r'shutdown',
            r'reboot',
            r':>',
        ]
        cmd_lower = command.lower()
        for pattern in dangerous_patterns:
            if re.search(pattern, cmd_lower):
                return {
                    'success': False,
                    'error': f'Dangerous command blocked: pattern matched {pattern}',
                    'exit_code': -1,
                }

        cwd = workdir or os.getcwd()
        env = {**os.environ, 'PYTHONIOENCODING': 'utf-8'}
        try:
            args = shlex.split(command, posix=(os.name != 'nt'))
        except ValueError:
            args = None

        try:
            if args:
                result = subprocess.run(
                    args,
                    capture_output=True,
                    text=True,
                    timeout=timeout,
                    cwd=cwd,
                    env=env,
                )
                return {
                    'success': result.returncode == 0,
                    'output': result.stdout,
                    'error': result.stderr,
                    'exit_code': result.returncode,
                }
            return {'success': False, 'error': f'Invalid command: {command}'}
        except subprocess.TimeoutExpired:
            return {'success': False, 'error': f'Command timed out after {timeout}s'}
        except Exception as e:
            return {'success': False, 'error': str(e)}


class WebSearchTool(Tool):
    """网页搜索工具"""
    
    name = "web_search"
    description = "搜索网页，返回结果摘要"
    input_schema = {
        "type": "object",
        "properties": {
            "query": {"type": "string", "description": "搜索关键词"},
            "max_results": {"type": "integer", "description": "最大结果数", "default": 5},
            "file_glob": {"type": "string", "description": "按文件类型过滤"},
        },
        "required": ["query"],
    }
    
    def execute(self, query: str, max_results: int = 5, file_glob: Optional[str] = None, max_age_minutes: Optional[int] = None, **kwargs) -> Dict[str, Any]:
        if not query:
            return {"success": False, "error": "query is required"}
        try:
            import requests
            import re
            import html
            import urllib.parse
        except Exception as exc:
            return {"success": False, "error": f"search dependencies missing: {exc}"}
        url = "https://html.duckduckgo.com/html/"
        headers = {
            "User-Agent": "Mozilla/5.0 (compatible; PRISM/1.0)",
            "Accept": "text/html",
        }
        try:
            resp = requests.post(url, data={"q": query}, headers=headers, timeout=20)
            text = resp.text
        except Exception as exc:
            return {"success": False, "error": f"search request failed: {exc}", "query": query}
        results: List[Dict[str, Any]] = []
        try:
            for block in re.findall(r'<a[^>]+class="result__a"[^>]*>(.*?)</a>', text, re.S)[:max_results]:
                title = re.sub(r"<[^>]+>", "", block)
                title = html.unescape(title).strip()
                href_match = re.search(r'href="([^"]+)"', block)
                link = href_match.group(1) if href_match else ""
                if link.startswith("//"):
                    link = "https:" + link
                snippet = ""
                snippet_match = re.search(r'<a[^>]+class="result__snippet"[^>]*>(.*?)</a>', text, re.S)
                if snippet_match:
                    snippet = html.unescape(re.sub(r"<[^>]+>", "", snippet_match.group(1))).strip()
                if title:
                    results.append({
                        "title": title,
                        "url": link,
                        "snippet": snippet,
                        "source": "duckduckgo",
                        "fetched_at": __import__('datetime').datetime.now().isoformat(),
                    })
        except Exception as exc:
            return {"success": False, "error": f"search parse failed: {exc}", "query": query}
        if not results:
            return {"success": True, "results": [], "query": query, "message": "no results"}
        
        if max_age_minutes is not None:
            from prism.tools.freshness import filter_stale_results
            results = filter_stale_results(results, max_age_minutes=max_age_minutes)
        return {"success": True, "results": results, "query": query, "count": len(results)}


class CodeExecutionTool(Tool):
    """代码执行工具"""
    
    name = "code_execution"
    description = "执行 Python 代码，支持超时和输出捕获"
    input_schema = {
        "type": "object",
        "properties": {
            "code": {"type": "string", "description": "Python 代码"},
            "timeout": {"type": "integer", "description": "超时秒数", "default": 30},
        },
        "required": ["code"],
    }
    
    def execute(self, code: str, timeout: int = 30, **kwargs) -> Dict[str, Any]:
        try:
            from prism.skills import skills
            skill = skills.get("code_execution")
            if skill and skill.handler:
                return skill.handler(code=code, timeout=timeout)
        except Exception as exc:
            logger.debug("code_execution skill invoke failed: %s", exc)
        return {"success": False, "error": "Code execution is not configured"}


# 浏览器工具（延迟注册，避免强依赖）
def _register_browser_tools(registry):
    """注册浏览器相关工具"""
    if not BROWSER_AVAILABLE:
        return
    
    class BrowserNavigateTool(Tool):
        name = "browser_navigate"
        description = "浏览器导航到指定URL"
        input_schema = {
            "type": "object",
            "properties": {
                "url": {"type": "string", "description": "目标URL"},
                "headless": {"type": "boolean", "description": "无头模式", "default": True},
            },
            "required": ["url"],
        }
        
        def execute(self, url: str, headless: bool = True) -> Dict[str, Any]:
            return browser_api.navigate(url, headless=headless)
    
    class BrowserSnapshotTool(Tool):
        name = "browser_snapshot"
        description = "获取页面快照/文本内容"
        input_schema = {
            "type": "object",
            "properties": {
                "full": {"type": "boolean", "description": "是否完整页面", "default": False},
            },
            "required": [],
        }
        
        def execute(self, full: bool = False) -> Dict[str, Any]:
            return browser_api.snapshot(full=full)
    
    class BrowserClickTool(Tool):
        name = "browser_click"
        description = "点击页面元素"
        input_schema = {
            "type": "object",
            "properties": {
                "selector": {"type": "string", "description": "CSS 选择器或 ref"},
            },
            "required": ["selector"],
        }
        
        def execute(self, selector: str) -> Dict[str, Any]:
            return browser_api.click(selector)
    
    class BrowserTypeTool(Tool):
        name = "browser_type"
        description = "在输入框中输入文本"
        input_schema = {
            "type": "object",
            "properties": {
                "selector": {"type": "string", "description": "CSS 选择器或 ref"},
                "text": {"type": "string", "description": "要输入的文本"},
            },
            "required": ["selector", "text"],
        }
        
        def execute(self, selector: str, text: str) -> Dict[str, Any]:
            return browser_api.type_text(selector, text)
    
    class BrowserScreenshotTool(Tool):
        name = "browser_screenshot"
        description = "浏览器截图"
        input_schema = {
            "type": "object",
            "properties": {
                "path": {"type": "string", "description": "截图保存路径（可选）"},
            },
            "required": [],
        }
        
        def execute(self, path: Optional[str] = None) -> Dict[str, Any]:
            return browser_api.screenshot(path)
    
    class BrowserEvaluateTool(Tool):
        name = "browser_evaluate"
        description = "执行JavaScript代码"
        input_schema = {
            "type": "object",
            "properties": {
                "script": {"type": "string", "description": "JavaScript 代码"},
            },
            "required": ["script"],
        }
        
        def execute(self, script: str) -> Dict[str, Any]:
            return browser_api.evaluate(script)
    
    class BrowserScrollTool(Tool):
        name = "browser_scroll"
        description = "滚动页面"
        input_schema = {
            "type": "object",
            "properties": {
                "direction": {"type": "string", "description": "up 或 down", "default": "down"},
            },
            "required": [],
        }
        
        def execute(self, direction: str = "down") -> Dict[str, Any]:
            return browser_api.scroll(direction)
    
    registry.register(BrowserNavigateTool())
    registry.register(BrowserSnapshotTool())
    registry.register(BrowserClickTool())
    registry.register(BrowserTypeTool())
    registry.register(BrowserScreenshotTool())
    registry.register(BrowserEvaluateTool())
    registry.register(BrowserScrollTool())


# 代码执行工具（延迟注册）
def _register_code_tools(registry):
    """注册代码执行相关工具"""
    if not CODE_EXECUTOR_AVAILABLE or _code_executor is None:
        return
    
    class CodeExecuteTool(Tool):
        name = "code_execution"
        description = "执行 Python 代码，支持超时和输出捕获"
        input_schema = {
            "type": "object",
            "properties": {
                "code": {"type": "string", "description": "Python 代码"},
                "timeout": {"type": "integer", "description": "超时秒数", "default": 30},
            },
            "required": ["code"],
        }
        
        def execute(self, code: str, timeout: int = 30, **kwargs) -> Dict[str, Any]:
            return _code_executor.execute(code, timeout=timeout)
    
    registry.register(CodeExecuteTool())


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
    
    def _validate(self, name: str, kwargs: Dict[str, Any]) -> Dict[str, Any]:
        tool = self._tools.get(name)
        if not tool:
            return kwargs
        schema = getattr(tool, 'input_schema', None) or {}
        required = schema.get('required') or []
        props = schema.get('properties') or {}
        missing = [p for p in required if p not in kwargs or kwargs.get(p) in (None, '')]
        if missing:
            return {'success': False, 'error': f'{name} missing params: {missing}', 'missing': missing}
        unknown = [k for k in kwargs.keys() if k not in props and k not in {'task_id', 'session_id'}]
        if unknown:
            return {'success': False, 'error': f'{name} unknown params: {unknown}', 'unknown': unknown}
        return kwargs
    
    def list_tools(self) -> List[Dict[str, Any]]:
        """列出所有工具"""
        return [
            {
                'name': t.name,
                'description': t.description,
                'inputSchema': t.input_schema or {'type': 'object', 'properties': {}},
            }
            for t in self._tools.values()
        ]
    
    def execute(self, name: str, **kwargs) -> Dict[str, Any]:
        """执行工具"""
        tool = self._tools.get(name)
        if not tool:
            return {'success': False, 'error': f'Tool not found: {name}'}
        validated = self._validate(name, kwargs)
        if isinstance(validated, dict) and not validated.get('success', True):
            return validated
        try:
            return tool.execute(**validated)
        except Exception as e:
            return {'success': False, 'error': str(e)}


# 全局工具注册表
registry = ToolRegistry()
_register_browser_tools(registry)
_register_code_tools(registry)
if "web_search" not in registry._tools:
    registry.register(WebSearchTool())
if "code_execution" not in registry._tools:
    registry.register(CodeExecutionTool())

try:
    from prism.tools.multimodal_tools import (
        VisionDescribeTool,
        ImageToBase64Tool,
        AudioTranscribeTool,
        TextToSpeechTool,
    )
    registry.register(VisionDescribeTool())
    registry.register(ImageToBase64Tool())
    registry.register(AudioTranscribeTool())
    registry.register(TextToSpeechTool())
except Exception as exc:
    logger.debug("multimodal tools import failed: %s", exc)

try:
    from prism.tools.gateway_manage import register as register_gateway_tools

    register_gateway_tools(registry)
except Exception as exc:
    logger.debug("gateway manage tools import failed: %s", exc)
