"""
PRISM Agent - Gateway 基础模块
避免循环导入
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Optional, Callable, Dict, Any
from datetime import datetime


@dataclass
class Message:
    """统一消息格式"""
    platform: str  # feishu | telegram | discord
    chat_id: str
    user_id: str
    text: str
    raw: Optional[Dict[str, Any]] = None
    timestamp: datetime = field(default_factory=datetime.now)
    message_type: str = "text"  # text | image | file | voice
    media_url: Optional[str] = None
    file_id: Optional[str] = None


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
