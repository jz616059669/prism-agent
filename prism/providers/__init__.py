"""PRISM Providers（安全导入：不触发 provider_pool 模块级初始化）"""
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from prism.providers.manager import ProviderPool, OpenAIProvider, Provider
    from prism.providers.fallback import FallbackManager
    from prism.providers.pool import CredentialPool

__all__ = [
    'ProviderPool',
    'OpenAIProvider',
    'Provider',
    'FallbackManager',
    'CredentialPool',
    'provider_pool',
]


def __getattr__(name: str):
    if name == 'provider_pool':
        from prism.providers.manager import provider_pool
        return provider_pool
    if name == 'ProviderPool':
        from prism.providers.manager import ProviderPool
        return ProviderPool
    if name == 'OpenAIProvider':
        from prism.providers.manager import OpenAIProvider
        return OpenAIProvider
    if name == 'Provider':
        from prism.providers.manager import Provider
        return Provider
    if name == 'FallbackManager':
        from prism.providers.fallback import FallbackManager
        return FallbackManager
    if name == 'CredentialPool':
        from prism.providers.pool import CredentialPool
        return CredentialPool
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
