"""
PRISM SDK - 独立于主包的外部工具/记忆/gateway 接口入口

用途：
- 外部插件/技能直接引用，避免依赖 prism 内部实现细节
- 第三方 agent 桥接到 PRISM 协议层
- 测试时 mock/stub 统一抽象

使用示例：
    from prism.sdk import Tool, MemoryProvider, PlatformAdapter
    from prism.sdk import tool_registry, memory_registry, gateway_registry
"""

from prism.interfaces import (
    Tool,
    MemoryProvider,
    MemoryRecord,
    PlatformAdapter,
    Message,
    ToolRegistry,
    MemoryProviderRegistry,
    GatewayRegistry,
)

__all__ = [
    "Tool",
    "MemoryProvider",
    "MemoryRecord",
    "PlatformAdapter",
    "Message",
    "ToolRegistry",
    "MemoryProviderRegistry",
    "GatewayRegistry",
]

# 预置统一注册表面向外部消费者
tool_registry: ToolRegistry = ToolRegistry()
memory_registry: MemoryProviderRegistry = MemoryProviderRegistry()
gateway_registry: GatewayRegistry = GatewayRegistry()
