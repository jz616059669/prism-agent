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
    callback_host: str = "127.0.0.1"
    callback_port: int = 9999


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
        """启动接收（企业微信部署回调服务）"""
        if not callable(handler):
            raise TypeError("handler must be callable")
        self.handler = handler
        self.running = True
        try:
            from http.server import HTTPServer, BaseHTTPRequestHandler
            import threading

            class WechatWebhookHandler(BaseHTTPRequestHandler):
                adapter = self

                def do_POST(self):
                    try:
                        import json as _json
                        length = int(self.headers.get('content-length', '0'))
                        body = self.rfile.read(length)
                        data = _json.loads(body.decode('utf-8')) if body else {}
                        msg = self.adapter._parse_callback(data)
                        if msg and self.adapter.handler:
                            self.adapter.handler(msg)
                        self.send_response(200)
                        self.end_headers()
                        self.wfile.write(b'ok')
                    except Exception as exc:
                        logger.debug("[Wechat] callback error: {exc}")
                        try:
                            self.send_response(500)
                            self.end_headers()
                            self.wfile.write(b'error')
                        except Exception:
                            pass

                def log_message(self, format, *args):
                    logger.debug("[Wechat] {args[0]}")

            host = self.config.callback_host
            server = HTTPServer((host, self.config.callback_port), WechatWebhookHandler)
            t = threading.Thread(target=server.serve_forever, daemon=True)
            t.start()
            logger.debug("[Wechat] callback service started on http://{server.server_address[0]}:{server.server_address[1]}")
        except Exception as exc:
            logger.debug("[Wechat] failed to start callback service: {exc}")
            self.running = False
            raise RuntimeError(f"企业微信回调服务启动失败: {exc}")

    def _parse_callback(self, data: Dict[str, Any]) -> Optional[Message]:
        """解析企业微信回调数据为 Message"""
        try:
            msg = data.get("msg") or data.get("message") or {}
            text = ""
            if isinstance(msg, dict):
                text = msg.get("content") or msg.get("text") or ""
            chat_id = msg.get("chatid") or msg.get("chat_id") or data.get("chatid") or ""
            user_id = msg.get("from") or data.get("from") or ""
            return Message(
                platform="wechat",
                chat_id=str(chat_id),
                user_id=str(user_id),
                text=str(text),
                raw=data,
            )
        except Exception as exc:
            logger.debug("[Wechat] parse callback failed: {exc}")
            return None

    def stop(self) -> None:
        self.running = False
        self.handler = None
