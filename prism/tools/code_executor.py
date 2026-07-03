"""
PRISM Agent - 代码执行沙箱
整合 Codex 的代码执行能力
支持 Python 脚本执行、输出捕获、超时控制
"""

import ast
import sys
import os
import tempfile
import subprocess
import json
from typing import Dict, Any, Optional, List
from io import StringIO
from contextlib import redirect_stdout, redirect_stderr


class SecurityError(Exception):
    pass


class CodeExecutor:
    """
    代码执行器
    支持：
    - Python 代码执行
    - 输出捕获
    - 超时控制
    - 安全限制（基于 AST 的静态检查）
    """
    
    def __init__(self, timeout: int = 30, max_output_length: int = 10000):
        self.timeout = timeout
        self.max_output_length = max_output_length
        self._forbidden_names = {
            '__import__',
            'exec',
            'eval',
            'compile',
            'open',
            'input',
            'breakpoint',
            'exit',
            'quit',
        }
        self._forbidden_modules = {
            'subprocess',
            'socket',
            'ctypes',
            'signal',
            'pty',
            'popen2',
            'commands',
            'asyncio',
            'multiprocessing',
            'threading',
            'os',
            'sys',
        }
    
    def execute(self, code: str, language: str = "python", timeout: int = 30) -> Dict[str, Any]:
        """
        执行代码
        
        Args:
            code: 代码内容
            language: 编程语言（目前只支持 python）
            timeout: 超时秒数
        """
        if language != "python":
            return {
                'success': False,
                'error': f'Unsupported language: {language}. Only Python is supported.'
            }
        
        # 安全检查
        security_check = self._security_check(code)
        if not security_check['safe']:
            return {
                'success': False,
                'error': f'Security violation: {security_check["reason"]}',
                'output': 'Code execution blocked for security reasons.'
            }
        
        # 创建临时文件
        with tempfile.NamedTemporaryFile(
            mode='w',
            suffix='.py',
            delete=False,
            encoding='utf-8'
        ) as f:
            f.write(code)
            temp_file = f.name
        
        try:
            # 执行代码
            result = subprocess.run(
                [sys.executable, temp_file],
                capture_output=True,
                text=True,
                timeout=timeout,
                cwd=os.getcwd(),
            )
            
            output = result.stdout
            error = result.stderr
            
            # 截断过长的输出
            if len(output) > self.max_output_length:
                output = output[:self.max_output_length] + "\n... (output truncated)"
            if len(error) > self.max_output_length:
                error = error[:self.max_output_length] + "\n... (error truncated)"
            
            return {
                'success': result.returncode == 0,
                'output': output,
                'error': error,
                'exit_code': result.returncode,
                'language': language,
            }
            
        except subprocess.TimeoutExpired:
            return {
                'success': False,
                'error': f'Code execution timed out after {timeout}s',
                'output': '',
                'language': language,
            }
        except Exception as e:
            return {
                'success': False,
                'error': str(e),
                'output': '',
                'language': language,
            }
        finally:
            # 清理临时文件
            try:
                os.unlink(temp_file)
            except Exception:
                logger.debug("temp file cleanup failed: %s", traceback.format_exc())
    
    def _security_check(self, code: str) -> Dict[str, Any]:
        """
        基于 AST 的安全检查，禁止危险操作
        
        规则：
        - 禁止导入危险模块
        - 禁止使用危险内置函数
        - 允许标准库中的安全操作（如 open 仅用于读取白名单路径）
        """
        try:
            tree = ast.parse(code)
        except SyntaxError as e:
            return {'safe': False, 'reason': f'Syntax error: {e}'}
        
        for node in ast.walk(tree):
            # 禁止危险内置函数调用
            if isinstance(node, ast.Name):
                if node.id in self._forbidden_names:
                    return {'safe': False, 'reason': f'Forbidden builtin: {node.id}'}
            
            # 禁止危险模块导入
            if isinstance(node, ast.Import):
                for alias in node.names:
                    top_pkg = alias.name.split('.')[0]
                    if top_pkg in self._forbidden_modules:
                        return {'safe': False, 'reason': f'Forbidden import: {alias.name}'}
            
            if isinstance(node, ast.ImportFrom):
                if node.module:
                    top_pkg = node.module.split('.')[0]
                    if top_pkg in self._forbidden_modules:
                        return {'safe': False, 'reason': f'Forbidden import: {node.module}'}
            
            # 禁止对危险模块的属性访问（如 os.system）
            if isinstance(node, ast.Attribute):
                if isinstance(node.value, ast.Name):
                    if node.value.id in self._forbidden_modules:
                        return {'safe': False, 'reason': f'Forbidden attribute access: {node.value.id}.{node.attr}'}
        
        return {'safe': True}
    
    def execute_with_context(self, code: str, context: Dict[str, Any]) -> Dict[str, Any]:
        """
        在指定上下文中执行代码
        
        Args:
            code: Python 代码
            context: 预定义的变量/函数
        
        Returns:
            执行结果
        """
        # 构建代码包装器
        context_str = "\n".join([f"{k} = {repr(v)}" for k, v in context.items()])
        full_code = f"{context_str}\n\n{code}"
        
        return self.execute(full_code)


# 全局代码执行器
code_executor = CodeExecutor()
