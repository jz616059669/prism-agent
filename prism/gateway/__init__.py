"""
PRISM Agent - Gateway 抽象层
支持多平台：飞书 / Telegram / Discord / 微信
"""

from abc import ABC, abstractmethod
from typing import Optional, Callable, Dict, Any
from dataclasses import dataclass
from datetime import datetime


@dataclass
class Message:
    """统一消息格式"""
    platform: str  # feishu | telegram | discord
    chat_id: str
    user_id: str
    text: str
    raw: Optional[Dict[str, Any]] = None
    timestamp: datetime = None
    
    def __post_init__(self):
        if self.timestamp is None:
            self.timestamp = datetime.now()


class PlatformAdapter(ABC):
    """平台适配器基类"""
    
    @abstractmethod
    def send(self, chat_id: str, text: str) -> bool:
        """发送消息"""
        pass
    
    @abstractmethod
    def start_polling(self, handler: Callable[[Message], None]):
        """开始接收消息"""
        pass
    
    @abstractmethod
    def stop(self):
        """停止接收"""
        pass


class Gateway:
    """
    统一 Gateway
    整合 Hermes 的多平台支持 + OpenClaw 的消息处理
    """
    
    def __init__(self):
        self.adapters: Dict[str, PlatformAdapter] = {}
        self.running = False
    
    def register(self, name: str, adapter: PlatformAdapter):
        """注册平台适配器"""
        self.adapters[name] = adapter
    
    def start(self, handler: Callable[[Message], None]):
        """启动所有平台"""
        self.running = True
        for name, adapter in self.adapters.items():
            try:
                adapter.start_polling(handler)
            except Exception as e:
                print(f"[Gateway] {name} 启动失败: {e}")
    
    def stop(self):
        """停止所有平台"""
        self.running = False
        for adapter in self.adapters.values():
            try:
                adapter.stop()
            except Exception:
                pass
    
    def send(self, platform: str, chat_id: str, text: str) -> bool:
        """通过指定平台发送消息"""
        adapter = self.adapters.get(platform)
        if not adapter:
            return False
        return adapter.send(chat_id, text)


# 全局 Gateway 实例
gateway = Gateway()
