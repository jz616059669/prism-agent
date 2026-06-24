"""
PRISM Agent - 真实模型调用验证
需要配置真实 API Key 后运行
"""

import os
import pytest

from prism.config import config as prism_config
from prism.providers.manager import provider_pool, ProviderPool


def test_provider_pool_empty_without_key():
    """未配置 API Key 时应明确报错"""
    pool = ProviderPool()
    result = pool.chat([{"role": "user", "content": "hi"}])
    assert result["success"] is False
    assert "未配置" in result["error"] or "提供商" in result["error"]


def test_provider_pool_with_env_key(monkeypatch):
    """环境变量提供 API Key 时应能创建 provider"""
    monkeypatch.setenv("OPENAI_API_KEY", "sk-test")
    monkeypatch.setenv("OPENAI_BASE_URL", "https://api.openai.com/v1")
    
    # 临时修改配置
    original_default = prism_config.get("model.default")
    original_provider = prism_config.get("model.provider")
    original_base_url = prism_config.get("model.base_url")
    original_api_key = prism_config.get("model.api_key")
    
    prism_config.set("model.default", "gpt-4o")
    prism_config.set("model.provider", "openai")
    prism_config.set("model.base_url", "https://api.openai.com/v1")
    prism_config.set("model.api_key", "sk-test")
    
    try:
        pool = ProviderPool()
        providers = pool.list_providers()
        assert "openai" in providers
        
        # is_available 会发起真实请求，这里只验证 provider 已加载
        assert len(pool.providers) > 0
    finally:
        # 恢复配置
        prism_config.set("model.default", original_default)
        prism_config.set("model.provider", original_provider)
        prism_config.set("model.base_url", original_base_url)
        prism_config.set("model.api_key", original_api_key)


def test_real_call_with_valid_key():
    """
    真实调用测试（需要有效 API Key）
    
    运行方式：
        set OPENAI_API_KEY=sk-... && pytest tests/test_real_model.py::test_real_call_with_valid_key -v
    """
    api_key = os.getenv("OPENAI_API_KEY") or prism_config.get("model.api_key")
    if not api_key:
        pytest.skip("未配置 API Key，跳过真实调用测试")
    
    pool = ProviderPool()
    result = pool.chat([{"role": "user", "content": "hi"}])
    
    assert result["success"] is True
    assert "content" in result
    assert len(result["content"]) > 0
    print(f"模型响应：{result['content'][:100]}")
    print(f"使用模型：{result.get('model')}")
    print(f"Token 用量：{result.get('usage')}")
