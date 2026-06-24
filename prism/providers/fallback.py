"""
PRISM Agent - 提供商自动降级
"""

from typing import List

from prism.providers.manager import ProviderPool, Provider


class FallbackManager:
    """
    自动降级管理器
    按顺序尝试提供商，直到成功
    """

    def __init__(self, fallback_chain: List[str]):
        self.fallback_chain = fallback_chain
        self._pool = ProviderPool()

    def resolve_providers(self) -> List[Provider]:
        """按降级顺序返回可用的 Provider 列表"""
        return list(self._pool.providers)


__all__ = ['FallbackManager']
