"""
PRISM Agent - 浏览器控制模块
整合 OpenClaw 的 CDP/Playwright 能力
"""

import asyncio
import json
import time
from typing import Optional, Dict, Any, List
from dataclasses import dataclass
from pathlib import Path

from prism.logging import logger
import traceback

try:
    from playwright.async_api import async_playwright, Page, Browser, BrowserContext
    PLAYWRIGHT_AVAILABLE = True
except ImportError:
    PLAYWRIGHT_AVAILABLE = False


@dataclass
class BrowserState:
    """浏览器状态"""
    url: str = ""
    title: str = ""
    screenshot_path: Optional[str] = None
    console_logs: List[str] = None
    
    def __post_init__(self):
        if self.console_logs is None:
            self.console_logs = []


class BrowserController:
    """
    浏览器控制器
    支持两种模式：
    1. Playwright（推荐）：跨平台、稳定、功能完整
    2. CDP（调试模式）：需要手动启动 Chrome --remote-debugging-port=9222
    """
    
    def __init__(self, mode: str = "playwright"):
        self.mode = mode
        self.playwright = None
        self.browser: Optional[Browser] = None
        self.context: Optional[BrowserContext] = None
        self.page: Optional[Page] = None
        self.state = BrowserState()
        self.connected = False
    
    async def connect(self, headless: bool = True) -> Dict[str, Any]:
        """
        连接浏览器
        headless: True=无头模式, False=显示界面
        """
        if not PLAYWRIGHT_AVAILABLE:
            return {
                'success': False,
                'error': 'Playwright not installed. Run: pip install playwright && playwright install chromium'
            }
        
        try:
            if self.playwright is None or not self.connected:
                self.playwright = await async_playwright().start()
                
                # 如果浏览器已存在但未连接，先关闭
                if self.browser and not self.connected:
                    try:
                        await self.browser.close()
                    except Exception:
                        pass
            
            # 启动浏览器
            if self.browser is None or self.browser.is_connected() is False:
                self.browser = await self.playwright.chromium.launch(
                    headless=headless,
                    args=['--no-sandbox', '--disable-setuid-sandbox']
                )
            
            # 创建上下文
            if self.context is None:
                self.context = await self.browser.new_context(
                    viewport={'width': 1280, 'height': 720},
                    user_agent='Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
                )
            
            # 创建页面
            if self.page is None or self.page.is_closed():
                self.page = await self.context.new_page()
                
                # 监听控制台日志
                self.page.on("console", lambda msg: self._handle_console(msg))
                
                # 监听页面错误
                self.page.on("pageerror", lambda err: self._handle_error(err))
            
            self.connected = True
            
            return {
                'success': True,
                'message': f'Browser connected ({self.mode} mode)',
                'mode': self.mode,
            }
            
        except Exception as e:
            return {
                'success': False,
                'error': f'Failed to connect browser: {str(e)}'
            }
    
    async def navigate(self, url: str) -> Dict[str, Any]:
        """导航到指定URL"""
        if not self._check_connection():
            return {'success': False, 'error': 'Browser not connected'}
        
        try:
            response = await self.page.goto(url, wait_until='domcontentloaded', timeout=30000)
            self.state.url = self.page.url
            self.state.title = await self.page.title()
            
            return {
                'success': True,
                'url': self.state.url,
                'title': self.state.title,
                'status': response.status if response else None,
            }
        except Exception as e:
            logger.debug("navigate failed: %s", traceback.format_exc())
            return {'success': False, 'error': str(e)}
    
    async def snapshot(self, full: bool = False) -> Dict[str, Any]:
        """获取页面快照（可访问性树）"""
        if not self._check_connection():
            return {'success': False, 'error': 'Browser not connected'}
        
        try:
            # 等待页面加载完成
            await self.page.wait_for_load_state('domcontentloaded', timeout=5000)
            await asyncio.sleep(0.5)  # 额外等待渲染
            
            # 获取页面文本内容
            body_text = await self.page.evaluate("() => document.body.textContent || ''")
            title = await self.page.title()
            url = self.page.url
            
            # 如果 textContent 为空，尝试 innerText
            if not body_text.strip():
                body_text = await self.page.evaluate("() => document.body.innerText || ''")
            
            # 如果仍然为空，尝试获取 outerHTML 作为兜底
            if not body_text.strip():
                outer_html = await self.page.evaluate("() => document.body.outerHTML || ''")
                if outer_html.strip():
                    body_text = "[页面文本为空，已返回 HTML 片段]\n" + outer_html[:4000]
                else:
                    body_text = "[页面文本为空，请检查页面是否正常渲染]"
            
            # 截断过长内容
            content = body_text.strip()
            if len(content) > 8000:
                content = content[:8000] + "\n... (content truncated)"
            
            return {
                'success': True,
                'content': content,
                'url': url,
                'title': title,
            }
            
        except Exception as e:
            logger.debug("snapshot failed: %s", traceback.format_exc())
            return {'success': False, 'error': str(e)}
    
    async def click(self, selector: str) -> Dict[str, Any]:
        """点击元素"""
        if not self._check_connection():
            return {'success': False, 'error': 'Browser not connected'}
        
        try:
            await self.page.click(selector, timeout=10000)
            await self.page.wait_for_load_state('domcontentloaded')
            
            return {
                'success': True,
                'action': 'click',
                'selector': selector,
            }
        except Exception as e:
            logger.debug("click failed: %s", traceback.format_exc())
            return {'success': False, 'error': str(e)}
    
    async def type_text(self, selector: str, text: str) -> Dict[str, Any]:
        """输入文本"""
        if not self._check_connection():
            return {'success': False, 'error': 'Browser not connected'}
        
        try:
            await self.page.fill(selector, text)
            return {
                'success': True,
                'action': 'type',
                'selector': selector,
                'text': text,
            }
        except Exception as e:
            logger.debug("type_text failed: %s", traceback.format_exc())
            return {'success': False, 'error': str(e)}
    
    async def screenshot(self, path: Optional[str] = None) -> Dict[str, Any]:
        """截图"""
        if not self._check_connection():
            return {'success': False, 'error': 'Browser not connected'}
        
        try:
            if not path:
                path = f"prism_screenshot_{int(time.time())}.png"
            
            await self.page.screenshot(path=path, full_page=False)
            self.state.screenshot_path = path
            
            return {
                'success': True,
                'path': path,
                'url': self.state.url,
            }
        except Exception as e:
            logger.debug("screenshot failed: %s", traceback.format_exc())
            return {'success': False, 'error': str(e)}
    
    async def evaluate(self, script: str) -> Dict[str, Any]:
        """执行JavaScript"""
        if not self._check_connection():
            return {'success': False, 'error': 'Browser not connected'}
        
        try:
            result = await self.page.evaluate(script)
            return {
                'success': True,
                'result': str(result)[:2000],
            }
        except Exception as e:
            logger.debug("evaluate failed: %s", traceback.format_exc())
            return {'success': False, 'error': str(e)}
    
    async def scroll(self, direction: str = "down") -> Dict[str, Any]:
        """滚动页面"""
        if not self._check_connection():
            return {'success': False, 'error': 'Browser not connected'}
        
        try:
            if direction == "down":
                await self.page.evaluate("window.scrollBy(0, 500)")
            elif direction == "up":
                await self.page.evaluate("window.scrollBy(0, -500)")
            else:
                return {'success': False, 'error': f'Unknown direction: {direction}'}
            
            return {'success': True, 'action': 'scroll', 'direction': direction}
        except Exception as e:
            logger.debug("scroll failed: %s", traceback.format_exc())
            return {'success': False, 'error': str(e)}
    
    async def disconnect(self) -> Dict[str, Any]:
        """断开连接"""
        try:
            if self.page:
                try:
                    await self.page.close()
                except Exception:
                    logger.debug("page close failed: %s", traceback.format_exc())
                self.page = None
            
            if self.context:
                try:
                    await self.context.close()
                except Exception:
                    logger.debug("context close failed: %s", traceback.format_exc())
                self.context = None
            
            if self.browser:
                try:
                    await self.browser.close()
                except Exception:
                    logger.debug("browser close failed: %s", traceback.format_exc())
                self.browser = None
            
            if self.playwright:
                try:
                    await self.playwright.stop()
                except Exception:
                    logger.debug("playwright stop failed: %s", traceback.format_exc())
                self.playwright = None
            
            self.connected = False
            self.state = BrowserState()
            
            return {'success': True, 'message': 'Browser disconnected'}
        except Exception as e:
            logger.debug("scroll failed: %s", traceback.format_exc())
            return {'success': False, 'error': str(e)}
    
    def _check_connection(self) -> bool:
        """检查连接状态"""
        return self.connected and self.page is not None
    
    def _handle_console(self, msg):
        """处理控制台消息"""
        self.state.console_logs.append(f"[{msg.type}] {msg.text}")
    
    def _handle_error(self, err):
        """处理页面错误"""
        self.state.console_logs.append(f"[ERROR] {str(err)}")


# 全局浏览器控制器
browser_controller = BrowserController()


# 同步接口封装（供非async代码调用）
_loop = None
_loop_lock = None

def _get_loop():
    """获取或创建持久事件循环"""
    global _loop, _loop_lock
    if _loop is None or _loop.is_closed():
        import threading
        _loop = asyncio.new_event_loop()
        _loop_lock = threading.Lock()
        threading.Thread(target=_loop.run_forever, daemon=True).start()
    return _loop

def run_async(coro):
    """在持久事件循环中运行异步函数，线程安全"""
    loop = _get_loop()
    future = asyncio.run_coroutine_threadsafe(coro, loop)
    return future.result(timeout=120)


# 同步API
class SyncBrowserAPI:
    """同步浏览器API（供工具系统调用）"""
    
    def _ensure_connected(self, headless: bool = True) -> bool:
        if not browser_controller.connected:
            result = run_async(browser_controller.connect(headless=headless))
            return result.get("success", False)
        return True
    
    def navigate(self, url: str, headless: bool = True) -> Dict[str, Any]:
        if not self._ensure_connected(headless):
            return {"success": False, "error": "Failed to connect browser"}
        return run_async(browser_controller.navigate(url))
    
    def snapshot(self, full: bool = False) -> Dict[str, Any]:
        if not browser_controller.connected:
            return {"success": False, "error": "Browser not connected"}
        return run_async(browser_controller.snapshot(full=full))
    
    def click(self, selector: str) -> Dict[str, Any]:
        if not browser_controller.connected:
            return {"success": False, "error": "Browser not connected"}
        return run_async(browser_controller.click(selector))
    
    def type(self, selector: str, text: str) -> Dict[str, Any]:
        if not browser_controller.connected:
            return {"success": False, "error": "Browser not connected"}
        return run_async(browser_controller.type_text(selector, text))
    
    def screenshot(self, path: Optional[str] = None) -> Dict[str, Any]:
        if not browser_controller.connected:
            return {"success": False, "error": "Browser not connected"}
        return run_async(browser_controller.screenshot(path))
    
    def evaluate(self, script: str) -> Dict[str, Any]:
        if not browser_controller.connected:
            return {"success": False, "error": "Browser not connected"}
        return run_async(browser_controller.evaluate(script))
    
    def scroll(self, direction: str = "down") -> Dict[str, Any]:
        if not browser_controller.connected:
            return {"success": False, "error": "Browser not connected"}
        return run_async(browser_controller.scroll(direction))
    
    def disconnect(self) -> Dict[str, Any]:
        if not browser_controller.connected:
            return {"success": True, "message": "Browser already disconnected"}
        return run_async(browser_controller.disconnect())


# 全局同步API
browser = SyncBrowserAPI()
