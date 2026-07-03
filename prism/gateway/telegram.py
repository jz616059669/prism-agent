"""
PRISM Agent - Telegram Gateway 适配器
"""

import json
import time
import requests
from typing import Optional, Callable, Dict, Any, List
from dataclasses import dataclass

from prism.gateway import PlatformAdapter, Message

from prism.logging import logger
import traceback


@dataclass
class TelegramConfig:
    """Telegram 配置"""
    bot_token: str
    base_url: str = "https://api.telegram.org/bot"


class TelegramAdapter(PlatformAdapter):
    """
    Telegram 适配器
    支持：
    - 发送消息
    - 长轮询 / Webhook
    """
    
    platform = "telegram"
    
    def __init__(self, config: TelegramConfig):
        self.config = config
        self.api_url = f"{config.base_url}{config.bot_token}"
        self.handler: Optional[Callable[[Message], None]] = None
        self.running = False
        self.last_update_id: int = 0
    
    def send(self, chat_id: str, text: str, parse_mode: str = "Markdown") -> bool:
        """
        发送消息
        
        Args:
            chat_id: 聊天 ID（用户 ID 或群组 ID）
            text: 消息文本
            parse_mode: 解析模式 (Markdown/HTML)
        """
        try:
            url = f"{self.api_url}/sendMessage"
            payload = {
                "chat_id": chat_id,
                "text": text,
                "parse_mode": parse_mode,
            }
            
            resp = requests.post(url, json=payload, timeout=10)
            resp.raise_for_status()
            data = resp.json()
            
            if data.get("ok"):
                print(f"[Telegram] 消息已发送 -> {chat_id}")
                return True
            else:
                print(f"[Telegram] 发送失败: {data}")
                return False
                
        except Exception as e:
            print(f"[Telegram] 发送消息异常: {e}")
            return False
    
    def start_polling(self, handler: Callable[[Message], None]):
        """启动长轮询"""
        self.handler = handler
        self.running = True
        
        print("[Telegram] 开始长轮询...")
        
        while self.running:
            try:
                self._poll_once()
                time.sleep(1)
            except KeyboardInterrupt:
                break
            except Exception as e:
                print(f"[Telegram] 轮询异常: {e}")
                time.sleep(5)
    
    def _poll_once(self):
        """单次轮询"""
        params = {
            "offset": self.last_update_id + 1,
            "timeout": 30,
        }
        
        try:
            resp = requests.get(
                f"{self.api_url}/getUpdates",
                params=params,
                timeout=35,
            )
            resp.raise_for_status()
            data = resp.json()
            
            if not data.get("ok"):
                return
            
            for update in data.get("result", []):
                self._handle_update(update)
                
        except Exception as e:
            print(f"[Telegram] 轮询失败: {e}")
    
    def _handle_update(self, update: Dict[str, Any]):
        """处理更新"""
        try:
            update_id = update.get("update_id", 0)
            self.last_update_id = max(self.last_update_id, update_id)
            
            message = update.get("message")
            if not message:
                return
            
            chat = message.get("chat", {})
            text = message.get("text", "")
            
            if not text:
                return
            
            msg = Message(
                platform="telegram",
                chat_id=str(chat.get("id", "")),
                user_id=str(message.get("from", {}).get("id", "")),
                text=text,
                raw=update,
            )
            
            if self.handler:
                self.handler(msg)
                
        except Exception as e:
            print(f"[Telegram] 处理更新失败: {e}")
    
    def stop(self):
        """停止轮询"""
        self.running = False
        self.handler = None
        print("[Telegram] 已停止")
    
    def set_webhook(self, url: str, allowed_updates: Optional[List[str]] = None) -> bool:
        """设置 Webhook"""
        payload = {"url": url}
        if allowed_updates:
            payload["allowed_updates"] = allowed_updates
        try:
            resp = requests.post(
                f"{self.api_url}/setWebhook",
                json=payload,
                timeout=10,
            )
            resp.raise_for_status()
            data = resp.json()
            if data.get("ok"):
                print(f"[Telegram] Webhook 已设置: {url}")
                return True
            print(f"[Telegram] Webhook 设置失败: {data}")
            return False
        except Exception as e:
            print(f"[Telegram] Webhook 设置异常: {e}")
            return False
    
    def delete_webhook(self) -> bool:
        """删除 Webhook"""
        try:
            resp = requests.post(f"{self.api_url}/deleteWebhook", timeout=10)
            resp.raise_for_status()
            data = resp.json()
            return data.get("ok", False)
        except Exception as e:
            print(f"[Telegram] Webhook 删除失败: {e}")
            return False
    
    def get_me(self) -> Dict[str, Any]:
        """获取 Bot 信息"""
        try:
            resp = requests.get(f"{self.api_url}/getMe", timeout=10)
            resp.raise_for_status()
            data = resp.json()
            if data.get("ok"):
                return {'success': True, 'bot': data["result"]}
            return {'success': False, 'error': data.get("description")}
        except Exception as e:
            return {'success': False, 'error': str(e)}

    def start_webhook(self, handler: Callable[[Message], None], host: str = "127.0.0.1", port: int = 9000):
        """启动本地 Webhook 服务接收 Telegram 更新"""
        self.handler = handler
        self.running = True
        import threading
        from http.server import HTTPServer, BaseHTTPRequestHandler

        class TelegramWebhookHandler(BaseHTTPRequestHandler):
            adapter = self

            def do_POST(self):
                try:
                    length = int(self.headers.get('content-length', '0'))
                    body = self.rfile.read(length)
                    data = json.loads(body.decode('utf-8'))
                    update = data.get("update_id")
                    if update:
                        self.adapter._handle_update(data)
                    self.send_response(200)
                    self.end_headers()
                    self.wfile.write(b'ok')
                except Exception as e:
                    print(f"[Telegram] webhook error: {e}")
                    try:
                        self.send_response(500)
                        self.end_headers()
                        self.wfile.write(b'error')
                    except Exception:
                        logger.debug("telegram send error response failed: %s", traceback.format_exc())

            def log_message(self, format, *args):
                print(f"[Telegram] {args[0]}")

        server = HTTPServer((host, port), TelegramWebhookHandler)
        t = threading.Thread(target=server.serve_forever, daemon=True)
        t.start()
        print(f"[Telegram] webhook 服务已启动：http://{host}:{port}/webhook/telegram")


def create_telegram_adapter(bot_token: str) -> TelegramAdapter:
    """创建 Telegram 适配器"""
    config = TelegramConfig(bot_token=bot_token)
    return TelegramAdapter(config)
