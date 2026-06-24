"""
PRISM Agent - Discord Gateway 适配器
"""

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
        
        注意：Discord 推荐使用 WebSocket Gateway，这里做占位
        生产环境推荐使用 discord.py 或 py-cord
        """
        self.handler = handler
        self.running = True
        
        print("[Discord] Gateway 连接待接入 discord.py / py-cord")
        print("[Discord] 当前为占位实现")
        
        # 演示模式
        print("[Discord] 建议使用 discord.py 库实现完整 Gateway")
    
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
