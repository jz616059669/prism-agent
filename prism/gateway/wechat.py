"""
PRISM Agent - 微信 Gateway 适配器（企业微信）
"""

from typing import Optional, Callable, Dict, Any
from dataclasses import dataclass, field

try:
    import requests
except Exception:  # pragma: no cover - optional dependency
    requests = None  # type: ignore

from prism.gateway import PlatformAdapter, Message
from prism.logging import logger


@dataclass
class WechatConfig:
    """企业微信配置"""
    corp_id: str
    agent_id: str
    secret: str
    token: Optional[str] = None
    encoding_aes_key: Optional[str] = None
    base_url: str = "https://qyapi.weixin.qq.com/cgi-bin"


class WechatAdapter(PlatformAdapter):
    """
    微信适配器（企业微信应用消息）
    支持：
    - 获取 access_token
    - 发送应用消息
    - 接收消息（需部署回调服务）
    """

    platform = "wechat"

    def __init__(self, config: WechatConfig):
        self.config = config
        self.handler: Optional[Callable[[Message], None]] = None
        self.running = False
        self._access_token: Optional[str] = None

    def _get_access_token(self) -> str:
        if self._access_token:
            return self._access_token

        if requests is None:
            raise RuntimeError("发送微信消息需要 requests，请先安装")
        
        url = f"{self.config.base_url}/gettoken"
        params = {
            "corpid": self.config.corp_id,
            "corpsecret": self.config.secret,
        }
        resp = requests.get(url, params=params, timeout=10)
        data = resp.json()
        if data.get("errcode") == 0:
            self._access_token = data["access_token"]
            return self._access_token

        raise RuntimeError(f"获取 access_token 失败: {data}")

    def send(self, chat_id: str, text: str) -> bool:
        """发送应用消息"""
        url = f"{self.config.base_url}/message/send"
        params = {"access_token": self._get_access_token()}
        payload = {
            "touser": chat_id,
            "msgtype": "text",
            "agentid": int(self.config.agent_id),
            "text": {"content": text},
        }
        resp = requests.post(url, params=params, json=payload, timeout=10)
        data = resp.json()
        if data.get("errcode") == 0:
            return True

        raise RuntimeError(f"发送消息失败: {data}")

    def start_polling(self, handler: Callable[[Message], None]) -> None:
        """启动接收（企业微信需部署回调服务）"""
        if not callable(handler):
            raise TypeError("handler must be callable")
        self.handler = handler
        raise NotImplementedError(
            "WeChat adapter callback service is not implemented yet. "
            "Deploy a callback service and route inbound events to the registered handler."
        )

    def stop(self) -> None:
        self.running = False
        self.handler = None
