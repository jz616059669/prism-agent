"""
PRISM Agent - 统一 Gateway
整合 Hermes 的多平台支持 + OpenClaw 的消息处理
"""

from prism.gateway.base import Message, PlatformAdapter
from typing import Callable


__all__ = ['Gateway', 'gateway', 'Message', 'PlatformAdapter']


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
        print(f"[Gateway] 已注册平台: {name}")
    
    def start(self, handler: Callable[[Message], None]):
        """
        启动所有平台
        
        Args:
            handler: 统一消息处理器，接收 Message 对象
        """
        self.running = True
        for name, adapter in self.adapters.items():
            try:
                adapter.start_polling(handler)
                print(f"[Gateway] {name} 启动成功")
            except Exception as e:
                print(f"[Gateway] {name} 启动失败: {e}")
    
    def stop(self):
        """停止所有平台"""
        self.running = False
        for name, adapter in self.adapters.items():
            try:
                adapter.stop()
                print(f"[Gateway] {name} 已停止")
            except Exception as e:
                print(f"[Gateway] {name} 停止失败: {e}")
    
    def send(self, platform: str, chat_id: str, text: str) -> bool:
        """
        通过指定平台发送消息
        
        Args:
            platform: 平台名称（feishu / telegram / discord）
            chat_id: 会话 ID
            text: 消息文本
        
        Returns:
            是否发送成功
        """
        adapter = self.adapters.get(platform)
        if not adapter:
            print(f"[Gateway] 未找到平台: {platform}")
            return False
        
        return adapter.send(chat_id, text)
    
    def list_platforms(self) -> list:
        """列出已注册的平台，并补充配置中存在的平台"""
        registered = list(self.adapters.keys())
        try:
            from prism.config import config as prism_config
            cfg_platforms = prism_config.get("gateway.platforms") or []
            for platform in cfg_platforms:
                if platform and platform not in registered:
                    registered.append(platform)
        except Exception:
            pass
        return registered


# 延迟初始化，避免循环导入
def _init_gateway():
    """初始化 Gateway 并注册默认平台"""
    g = Gateway()
    
    # 注意：这里不自动注册，需要用户手动配置
    # 示例：
    # from prism.gateway.feishu import create_feishu_adapter
    # g.register("feishu", create_feishu_adapter(app_id, app_secret))
    
    return g


# 全局 Gateway 实例
gateway = _init_gateway()
