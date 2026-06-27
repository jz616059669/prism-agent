"""
PRISM Agent - Discord Gateway 适配器
"""

import threading
import time
import requests
from typing import Optional, Callable, Dict, Any, List
from dataclasses import dataclass

from prism.gateway import PlatformAdapter, Message


@dataclass
class DiscordConfig:
    """Discord 配置"""
    bot_token: str
    application_id: Optional[str] = None
    base_url: str = "https://discord.com/api/v10"


class DiscordAdapter(PlatformAdapter):
    """
    Discord 适配器
    支持：
    - Gateway Intents（消息内容、@用户）
    - 发送消息、回复消息
    - Webhook
    """
    
    platform = "discord"
    
    def __init__(self, config: DiscordConfig):
        self.config = config
        self.headers = {
            "Authorization": f"Bot {config.bot_token}",
            "Content-Type": "application/json",
        }
        self.handler: Optional[Callable[[Message], None]] = None
        self.running = False
    
    def send(self, chat_id: str, text: str) -> bool:
        """
        发送消息
        
        Args:
            chat_id: 频道 ID 或用户 ID
            text: 消息文本（Discord 最多 2000 字）
        """
        try:
            # Discord 消息上限 2000
            if len(text) > 2000:
                text = text[:1997] + "..."
            
            url = f"{self.config.base_url}/channels/{chat_id}/messages"
            payload = {"content": text}
            
            resp = requests.post(url, json=payload, headers=self.headers, timeout=10)
            resp.raise_for_status()
            data = resp.json()
            
            print(f"[Discord] 消息已发送 -> {chat_id}")
            return True
                
        except Exception as e:
            print(f"[Discord] 发送消息异常: {e}")
            return False
    
    def start_polling(self, handler: Callable[[Message], None]):
        """
        启动 Gateway 连接

        实际使用请安装 websockets：
        pip install websockets
        """
        self.handler = handler
        self.running = True

        try:
            import websockets
            import asyncio
            import json as _json

            async def _connect():
                url = "wss://gateway.discord.gg/?v=10&encoding=json"
                async with websockets.connect(url) as ws:
                    hello = _json.loads(await ws.recv())
                    heartbeat = hello.get("d", {}).get("heartbeat_interval", 45000)
                    await ws.send(_json.dumps({
                        "op": 2,
                        "d": {
                            "token": self.config.bot_token,
                            "intents": 3328,
                            "properties": {"os": "linux", "browser": "prism", "device": "prism"},
                        }
                    }))
                    last = 0
                    while self.running:
                        try:
                            msg = await asyncio.wait_for(ws.recv(), timeout=heartbeat / 1000)
                            data = _json.loads(msg)
                            if data.get("op") == 11:
                                await ws.send(_json.dumps({"op": 1, "d": last}))
                                continue
                            if data.get("t") == "MESSAGE_CREATE":
                                m = data.get("d", {})
                                if handler:
                                    handler(Message(
                                        platform="discord",
                                        chat_id=str(m.get("channel_id", "")),
                                        user_id=str(m.get("author", {}).get("id", "")),
                                        text=m.get("content", ""),
                                        raw=data,
                                    ))
                        except asyncio.TimeoutError:
                            await ws.send(_json.dumps({"op": 1, "d": last}))

            def _run():
                asyncio.run(_connect())

            t = threading.Thread(target=_run, daemon=True)
            t.start()
            print("[Discord] Gateway WebSocket 已启动")
        except Exception as e:
            print(f"[Discord] 启动失败: {e}")
            print("[Discord] 请安装 websockets：pip install websockets")
    
    def stop(self):
        """停止"""
        self.running = False
        self.handler = None
        print("[Discord] 已停止")
    
    def get_channel_messages(self, channel_id: str, limit: int = 10) -> Dict[str, Any]:
        """获取频道消息历史"""
        try:
            url = f"{self.config.base_url}/channels/{channel_id}/messages"
            params = {"limit": min(limit, 100)}
            
            resp = requests.get(url, params=params, headers=self.headers, timeout=10)
            resp.raise_for_status()
            data = resp.json()
            
            return {
                'success': True,
                'messages': data,
            }
        except Exception as e:
            return {'success': False, 'error': str(e)}
    
    def create_webhook(self, channel_id: str, name: str) -> Dict[str, Any]:
        """创建 Webhook"""
        try:
            url = f"{self.config.base_url}/channels/{channel_id}/webhooks"
            payload = {"name": name}
            
            resp = requests.post(url, json=payload, headers=self.headers, timeout=10)
            resp.raise_for_status()
            data = resp.json()
            
            return {
                'success': True,
                'webhook': data,
            }
        except Exception as e:
            return {'success': False, 'error': str(e)}
    
    def get_current_user(self) -> Dict[str, Any]:
        """获取当前 Bot 用户信息"""
        try:
            resp = requests.get(
                f"{self.config.base_url}/users/@me",
                headers=self.headers,
                timeout=10,
            )
            resp.raise_for_status()
            data = resp.json()
            
            return {
                'success': True,
                'user': data,
            }
        except Exception as e:
            return {'success': False, 'error': str(e)}


def create_discord_adapter(bot_token: str, application_id: Optional[str] = None) -> DiscordAdapter:
    """创建 Discord 适配器"""
    config = DiscordConfig(
        bot_token=bot_token,
        application_id=application_id,
    )
    return DiscordAdapter(config)
