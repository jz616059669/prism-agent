"""
PRISM Agent - 微信 Gateway 适配器（骨架）
后续可按实际协议接入企业微信/公众号/微信客服
"""

from dataclasses import dataclass, field
from typing import Optional, Callable, Dict, Any
from datetime import datetime

from prism.gateway import PlatformAdapter, Message


@dataclass
class WechatConfig:
    """微信配置"""
    app_id: str
    app_secret: str
    token: Optional[str] = None
    encoding_aes_key: Optional[str] = None
    base_url: str = "https://api.weixin.qq.com/cgi-bin"


class WechatAdapter(PlatformAdapter):
    """
    微信适配器（骨架）
    支持后续接入：
    - 企业微信应用消息
    - 公众号模板消息
    - 微信客服消息
    """

    platform = "wechat"

    def __init__(self, config: WechatConfig):
        self.config = config
        self.handler: Optional[Callable[[Message], None]] = None
        self.running = False

    def send(self, chat_id: str, text: str) -> bool:
        raise NotImplementedError("微信发送待接入真实协议")

    def start_polling(self, handler: Callable[[Message], None]):
        self.handler = handler
        self.running = True
        # TODO: 接入真实接收逻辑

    def stop(self):
        self.running = False
        self.handler = None
