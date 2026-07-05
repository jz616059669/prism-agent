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
from typing import Dict, List, Any, Optional, Callable
from abc import ABC, abstractmethod
from pathlib import Path

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
            
            # 安全检查：禁止明显危险的命令模式
            dangerous_patterns = [
                r'rm\s+-rf\s+/',
                r'del\s+/[fs]',
                r'format\s+[c-z]:',
                r'shutdown',
                r'reboot',
                r':>',  # Windows 重定向破坏
            ]
            cmd_lower = command.lower()
            for pattern in dangerous_patterns:
                if re.search(pattern, cmd_lower):
                    return {
                        'success': False,
                        'error': f'Dangerous command blocked: pattern matched {pattern}',
                        'exit_code': -1,
                    }
            
            # 使用 shlex.split 解析命令，避免 shell=True
            if os.name == 'nt':
                # Windows 下尽量用参数数组，避免 shell 注入
                import shlex
                try:
                    args = shlex.split(command, posix=False)
                    if not args:
                        return {'success': False, 'error': 'Empty command'}
                    result = subprocess.run(
                        args,
                        capture_output=True,
                        text=True,
                        timeout=timeout,
                        cwd=cwd,
                        env={**os.environ, 'PYTHONIOENCODING': 'utf-8'},
                    )
                except ValueError:
                    # 回退：复杂 shell 语法仍允许 shell=True，但做长度限制
                    if len(command) > 4096:
                        return {'success': False, 'error': 'Command too long (max 4096 chars)', 'exit_code': -1}
                    result = subprocess.run(
                        command,
                        shell=True,
                        capture_output=True,
                        text=True,
                        timeout=timeout,
                        cwd=cwd,
                        env={**os.environ, 'PYTHONIOENCODING': 'utf-8'},
                    )
            else:
                # Unix 下尽量用 shlex 避免 shell 注入
                try:
                    args = shlex.split(command)
                    if not args:
                        return {'success': False, 'error': 'Empty command'}
                    result = subprocess.run(
                        args,
                        capture_output=True,
                        text=True,
                        timeout=timeout,
                        cwd=cwd,
                        env={**os.environ, 'PYTHONIOENCODING': 'utf-8'},
                    )
                except ValueError:
                    # 回退：复杂 shell 语法仍允许 shell=True
                    if len(command) > 4096:
                        return {'success': False, 'error': 'Command too long (max 4096 chars)', 'exit_code': -1}
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


class WebSearchTool(Tool):
    """网页搜索工具，使用 DuckDuckGo HTML 版，无需 API key"""
    
    name = "web_search"
    description = "搜索网页，返回结果摘要"
    
    def execute(self, query: str, max_results: int = 5, max_age_minutes: int = 60) -> Dict[str, Any]:
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
        
        from prism.tools.freshness import filter_stale_results
        results = filter_stale_results(results, max_age_minutes=max_age_minutes)
        return {"success": True, "results": results, "query": query, "count": len(results)}


class CodeExecutionTool(Tool):
    """代码执行工具，透传 skills.code_execution"""
    
    name = "code_execution"
    description = "执行 Python 代码，返回结果"
    
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
        
        def execute(self, url: str, headless: bool = True) -> Dict[str, Any]:
            return browser_api.navigate(url, headless=headless)
    
    class BrowserSnapshotTool(Tool):
        name = "browser_snapshot"
        description = "获取页面快照/文本内容"
        
        def execute(self, full: bool = False) -> Dict[str, Any]:
            return browser_api.snapshot(full=full)
    
    class BrowserClickTool(Tool):
        name = "browser_click"
        description = "点击页面元素"
        
        def execute(self, selector: str) -> Dict[str, Any]:
            return browser_api.click(selector)
    
    class BrowserTypeTool(Tool):
        name = "browser_type"
        description = "在输入框中输入文本"
        
        def execute(self, selector: str, text: str) -> Dict[str, Any]:
            return browser_api.type_text(selector, text)
    
    class BrowserScreenshotTool(Tool):
        name = "browser_screenshot"
        description = "浏览器截图"
        
        def execute(self, path: Optional[str] = None) -> Dict[str, Any]:
            return browser_api.screenshot(path)
    
    class BrowserEvaluateTool(Tool):
        name = "browser_evaluate"
        description = "执行JavaScript代码"
        
        def execute(self, script: str) -> Dict[str, Any]:
            return browser_api.evaluate(script)
    
    class BrowserScrollTool(Tool):
        name = "browser_scroll"
        description = "滚动页面"
        
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
_register_browser_tools(registry)
_register_code_tools(registry)
if "web_search" not in registry._tools:
    registry.register(WebSearchTool())
if "code_execution" not in registry._tools:
    registry.register(CodeExecutionTool())
