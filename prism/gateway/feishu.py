"""
PRISM Agent - 飞书 Gateway 适配器
整合 Hermes 的飞书 Gateway 能力
"""

import json
import time
import hmac
import hashlib
import requests
from typing import Optional, Callable, Dict, Any, List
from dataclasses import dataclass

from prism.gateway import PlatformAdapter, Message


@dataclass
class FeishuConfig:
    """飞书配置"""
    app_id: str
    app_secret: str
    encrypt_key: Optional[str] = None
    verification_token: Optional[str] = None
    base_url: str = "https://open.feishu.cn/open-apis"


class FeishuAdapter(PlatformAdapter):
    """
    飞书适配器
    支持：
    - 接收消息（Webhook / 长轮询）
    - 发送消息
    - 获取用户信息
    """
    
    platform = "feishu"
    
    def __init__(self, config: FeishuConfig):
        self.config = config
        self.access_token: Optional[str] = None
        self.token_expires_at: float = 0
        self.handler: Optional[Callable[[Message], None]] = None
        self.running = False
    
    def _get_tenant_access_token(self) -> str:
        """
        获取 tenant_access_token
        自动刷新过期 token
        """
        # 如果 token 还有 5 分钟过期，先刷新
        if self.access_token and time.time() < self.token_expires_at - 300:
            return self.access_token
        
        url = f"{self.config.base_url}/auth/v3/tenant_access_token/internal"
        payload = {
            "app_id": self.config.app_id,
            "app_secret": self.config.app_secret,
        }
        
        try:
            resp = requests.post(url, json=payload, timeout=10)
            resp.raise_for_status()
            data = resp.json()
            
            if data.get("code") == 0:
                self.access_token = data["tenant_access_token"]
                # expire 是秒数，转换为时间戳
                self.token_expires_at = time.time() + data.get("expire", 7200)
                return self.access_token
            else:
                raise Exception(f"Failed to get token: {data}")
        except Exception as e:
            print(f"[Feishu] 获取 token 失败: {e}")
            raise
    
    def send(self, chat_id: str, text: str) -> bool:
        """
        发送消息
        
        Args:
            chat_id: 会话 ID（可以是 open_id、user_id、group_id）
            text: 消息文本
        """
        try:
            token = self._get_tenant_access_token()
            
            url = f"{self.config.base_url}/im/v1/messages"
            params = {"receive_id_type": "chat_id"}
            headers = {
                "Authorization": f"Bearer {token}",
                "Content-Type": "application/json; charset=utf-8",
            }
            payload = {
                "receive_id": chat_id,
                "msg_type": "text",
                "content": json.dumps({"text": text}, ensure_ascii=False),
            }
            
            resp = requests.post(url, params=params, json=payload, 
                                headers=headers, timeout=10)
            resp.raise_for_status()
            data = resp.json()
            
            if data.get("code") == 0:
                print(f"[Feishu] 消息已发送 -> {chat_id}")
                return True
            else:
                print(f"[Feishu] 发送失败: {data}")
                return False
                
        except Exception as e:
            print(f"[Feishu] 发送消息异常: {e}")
            return False
    
    def start_polling(self, handler: Callable[[Message], None]):
        """
        启动长轮询接收消息

        注意：飞书推荐使用 Webhook，长轮询仅作演示
        生产环境请部署 Webhook 服务
        """
        self.handler = handler
        self.running = True

        print("[Feishu] 开始轮询消息（演示模式）...")
        print("[Feishu] 生产环境请部署 Webhook 服务")

        # 演示模式：模拟接收
        # 实际应该连接飞书 Webhook 或长轮询
        # 这里先打印提示
        print("[Feishu] 轮询服务待接入 Webhook endpoint")

    def start_webhook(self, handler: Callable[[Message], None], host: str = "127.0.0.1", port: int = 9000):
        """
        启动本地 Webhook 服务接收飞书事件
        """
        self.handler = handler
        self.running = True

        import json as _json
        import threading
        from http.server import HTTPServer, BaseHTTPRequestHandler

        class FeishuWebhookHandler(BaseHTTPRequestHandler):
            adapter = self

            def do_POST(self):
                try:
                    length = int(self.headers.get('content-length', '0'))
                    body = self.rfile.read(length)
                    data = _json.loads(body.decode('utf-8'))
                    timestamp = self.headers.get('X-Lark-Request-Timestamp', '')
                    nonce = self.headers.get('X-Lark-Request-Nonce', '')
                    signature = self.headers.get('X-Lark-Signature', '')

                    verified = True
                    if self.adapter.config.encrypt_key:
                        verified = self.adapter.verify_webhook(body, timestamp, nonce, signature)

                    if not verified:
                        self.send_response(403)
                        self.end_headers()
                        self.wfile.write(b'forbidden')
                        return

                    msg = self.adapter.parse_event(data)
                    if msg and self.adapter.handler:
                        self.adapter.handler(msg)

                    self.send_response(200)
                    self.end_headers()
                    self.wfile.write(b'ok')
                except Exception as e:
                    import traceback
                    print(f"[Feishu] webhook error: {e}")
                    traceback.print_exc()
                    try:
                        self.send_response(500)
                        self.end_headers()
                        self.wfile.write(b'error')
                    except Exception:
                        pass

            def log_message(self, format, *args):
                print(f"[Feishu] {args[0]}")

        server = HTTPServer((host, port), FeishuWebhookHandler)
        t = threading.Thread(target=server.serve_forever, daemon=True)
        t.start()
        print(f"[Feishu] webhook 服务已启动：http://{host}:{port}/webhook/feishu")
    
    def stop(self):
        """停止接收"""
        self.running = False
        self.handler = None
        print("[Feishu] 已停止")
    
    def get_user_info(self, open_id: str) -> Dict[str, Any]:
        """获取用户信息"""
        try:
            token = self._get_tenant_access_token()
            url = f"{self.config.base_url}/contact/v3/users/{open_id}"
            params = {"user_id_type": "open_id"}
            headers = {"Authorization": f"Bearer {token}"}
            
            resp = requests.get(url, params=params, headers=headers, timeout=10)
            resp.raise_for_status()
            data = resp.json()
            
            if data.get("code") == 0:
                return {
                    'success': True,
                    'user': data["data"]["user"],
                }
            else:
                return {'success': False, 'error': data.get("msg")}
        except Exception as e:
            return {'success': False, 'error': str(e)}
    
    def verify_webhook(self, body: bytes, timestamp: str, nonce: str, 
                       signature: str) -> bool:
        """
        验证 Webhook 签名
        
        Args:
            body: 请求体
            timestamp: 时间戳
            nonce: 随机字符串
            signature: 签名
        """
        if not self.config.encrypt_key:
            return False
        
        try:
            # 拼接字符串
            bytes_before = (timestamp + nonce + self.config.encrypt_key).encode()
            # SHA256 加密
            sign = hashlib.sha256(bytes_before).hexdigest()
            return sign == signature
        except Exception:
            return False
    
    def parse_event(self, body: Dict[str, Any]) -> Optional[Message]:
        """
        解析飞书事件
        
        Args:
            body: 飞书事件 JSON
        """
        try:
            header = body.get("header", {})
            event = body.get("event", {})
            
            if header.get("event_type") != "im.message.receive_v1":
                return None
            
            message = event.get("message", {})
            sender = event.get("sender", {}).get("sender_id", {})
            
            return Message(
                platform="feishu",
                chat_id=message.get("chat_id", ""),
                user_id=sender.get("open_id", ""),
                text=self._extract_text(message),
                raw=body,
            )
        except Exception as e:
            print(f"[Feishu] 解析事件失败: {e}")
            return None
    
    def _extract_text(self, message: Dict[str, Any]) -> str:
        """提取消息文本"""
        msg_type = message.get("message_type", "")
        
        if msg_type == "text":
            content = message.get("content", "{}")
            try:
                data = json.loads(content)
                return data.get("text", "")
            except Exception:
                return content
        elif msg_type == "interactive":
            return "[卡片消息]"
        elif msg_type == "image":
            return "[图片]"
        elif msg_type == "file":
            return "[文件]"
        else:
            return f"[{msg_type}消息]"


# 便捷函数
def create_feishu_adapter(app_id: str, app_secret: str, 
                          encrypt_key: Optional[str] = None) -> FeishuAdapter:
    """创建飞书适配器"""
    config = FeishuConfig(
        app_id=app_id,
        app_secret=app_secret,
        encrypt_key=encrypt_key,
    )
    return FeishuAdapter(config)
