"""
PRISM Agent - 提供商自动降级
"""

from typing import List

from prism.providers.manager import ProviderPool, Provider
from prism.logging import logger


class FallbackManager:
    """
    自动降级管理器
    按 fallback_chain 顺序尝试提供商，直到成功
    """

    def __init__(self, fallback_chain: List[str], pool: ProviderPool | None = None):
        self.fallback_chain = fallback_chain
        self._pool = pool or ProviderPool()

    def resolve_providers(self) -> List[Provider]:
        """按降级链过滤可用 Provider，未匹配时返回全部。"""
        providers = list(self._pool.providers)
        if not self.fallback_chain:
            return providers
        chain_names = [name.split("/")[0].lower() for name in self.fallback_chain]
        matched = [p for p in providers if p.name.lower() in chain_names]
        if not matched:
            logger.warning("fallback chain %s matched no providers, using all", self.fallback_chain)
            return providers
        return matched

    def chat(self, messages: List[dict], **kwargs) -> dict:
        """按降级链顺序调用 provider.chat，全部失败返回最后错误。"""
        providers = self.resolve_providers()
        if not providers:
            return {
                "success": False,
                "error": "未配置可用模型提供商。请先在 ~/.prism/config.yaml 填写 model.api_key。",
            }
        last_error = None
        for provider in providers:
            try:
                result = provider.chat(messages, **kwargs)
                if result.get("success"):
                    return result
                last_error = result.get("error")
            except Exception as exc:
                logger.debug("provider %s fallback failed: %s", provider.name, exc)
                last_error = str(exc)
        return {
            "success": False,
            "error": last_error or "所有 fallback provider 均失败",
        }


__all__ = ["FallbackManager"]
