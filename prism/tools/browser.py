"""
PRISM Agent - 浏览器控制模块
整合 OpenClaw 的 CDP/Playwright 能力
"""

import asyncio
import json
import threading
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
                        logger.debug("browser close failed: %s", traceback.format_exc())
            
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
            
            # 如果仍然为空，尝试更轻量的提示，不再直接塞大段 HTML
            if not body_text.strip():
                body_text = "[页面文本为空，请检查页面是否正常渲染或尝试截图查看]"
            
            # 截断过长内容
            content = body_text.strip()
            if len(content) > 8000:
                content = content[:8000] + "\n... (content truncated)"
            
            return {
                'success': True,
                'content': content,
                'url': url,
                'title': title,
                'role': 'browser',
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
    
    async def screenshot(self, path: Optional[str] = None, full_page: bool = False) -> Dict[str, Any]:
        """截图"""
        if not self._check_connection():
            return {'success': False, 'error': 'Browser not connected'}
        
        try:
            if not path:
                screenshot_dir = Path.home() / '.prism' / 'browser_screenshots'
                screenshot_dir.mkdir(parents=True, exist_ok=True)
                path = str(screenshot_dir / f"prism_screenshot_{int(time.time())}.png")
            
            await self.page.screenshot(path=path, full_page=full_page)
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
            logger.debug("disconnect failed: %s", traceback.format_exc())
            return {'success': False, 'error': str(e)}
    
    def _check_connection(self) -> bool:
        if not self.connected:
            return False
        if self.page is None:
            return False
        try:
            return self.page.is_closed() is False
        except Exception:
            return False
    
    def _handle_console(self, msg):
        """处理控制台消息"""
        self.state.console_logs.append(f"[{msg.type}] {msg.text}")
    
    def _handle_error(self, err):
        """处理页面错误"""
        self.state.console_logs.append(f"[ERROR] {str(err)}")


# 全局浏览器控制器
browser_controller = BrowserController()


# 同步接口封装（供非async代码调用）
class SyncBrowserAPI:
    """同步浏览器API（供工具系统调用）"""
    
    def __init__(self):
        self._loop: Optional[asyncio.AbstractEventLoop] = None
        self._loop_thread: Optional[threading.Thread] = None
        self._ensure_loop()
    
    def _ensure_loop(self) -> None:
        if self._loop is not None and not self._loop.is_closed():
            return
        self._loop = asyncio.new_event_loop()
        self._loop_thread = threading.Thread(target=self._loop.run_forever, daemon=True)
        self._loop_thread.start()
    
    def _shutdown_loop(self) -> None:
        if self._loop is None or self._loop.is_closed():
            return
        try:
            self._loop.call_soon_threadsafe(self._loop.stop)
        except Exception:
            pass
        if self._loop_thread is not None:
            self._loop_thread.join(timeout=5)
        self._loop = None
        self._loop_thread = None
    
    def _run(self, coro, timeout: int = 120):
        self._ensure_loop()
        loop = self._loop
        future = asyncio.run_coroutine_threadsafe(coro, loop)
        try:
            return future.result(timeout=timeout)
        except Exception:
            try:
                self._run(browser_controller.disconnect())
            except Exception:
                pass
            return {"success": False, "error": f"browser operation timed out after {timeout}s"}
    
    def _ensure_connected(self, headless: bool = True) -> bool:
        if not self._check_connection():
            try:
                result = self._run(browser_controller.connect(headless=headless))
                return result.get("success", False)
            except Exception:
                return False
        return True
    
    def navigate(self, url: str, headless: bool = True) -> Dict[str, Any]:
        if not self._ensure_connected(headless):
            return {"success": False, "error": "Failed to connect browser"}
        return self._run(browser_controller.navigate(url), timeout=40)
    
    def snapshot(self, full: bool = False) -> Dict[str, Any]:
        if not browser_controller.connected:
            return {"success": False, "error": "Browser not connected"}
        return self._run(browser_controller.snapshot(full=full), timeout=40)
    
    def click(self, selector: str) -> Dict[str, Any]:
        if not browser_controller.connected:
            return {"success": False, "error": "Browser not connected"}
        return self._run(browser_controller.click(selector), timeout=20)
    
    def type(self, selector: str, text: str) -> Dict[str, Any]:
        if not browser_controller.connected:
            return {"success": False, "error": "Browser not connected"}
        return self._run(browser_controller.type_text(selector, text), timeout=20)
    
    def screenshot(self, path: Optional[str] = None) -> Dict[str, Any]:
        if not browser_controller.connected:
            return {"success": False, "error": "Browser not connected"}
        return self._run(browser_controller.screenshot(path), timeout=20)
    
    def evaluate(self, script: str) -> Dict[str, Any]:
        if not browser_controller.connected:
            return {"success": False, "error": "Browser not connected"}
        return self._run(browser_controller.evaluate(script), timeout=20)
    
    def scroll(self, direction: str = "down") -> Dict[str, Any]:
        if not browser_controller.connected:
            return {"success": False, "error": "Browser not connected"}
        return self._run(browser_controller.scroll(direction), timeout=20)
    
    def disconnect(self) -> Dict[str, Any]:
        if not browser_controller.connected:
            return {"success": True, "message": "Browser already disconnected"}
        result = self._run(browser_controller.disconnect())
        self._shutdown_loop()
        return result
    
    def __del__(self):
        try:
            self._shutdown_loop()
        except Exception:
            pass


# 全局同步API
browser = SyncBrowserAPI()
