"""
PRISM Agent - 模型提供商管理
整合多模型、自动降级、凭证池轮转
"""

import os
import time
from typing import Optional, List, Dict, Any
from abc import ABC, abstractmethod
from openai import OpenAI
import httpx


class Provider(ABC):
    """提供商基类"""
    
    @abstractmethod
    def chat(self, messages: List[Dict], **kwargs) -> Dict[str, Any]:
        """发送聊天请求"""
        pass
    
    @abstractmethod
    def is_available(self) -> bool:
        """检查提供商是否可用"""
        pass


class OpenAIProvider(Provider):
    """OpenAI 兼容提供商（支持 OpenAI/DeepSeek/StepFun/本地模型等）"""
    
    def __init__(self, name: str, base_url: str, api_key: str, model: str):
        self.name = name
        self.base_url = base_url.rstrip('/')
        self.api_key = api_key
        self.model = model
        self.client = OpenAI(
            base_url=f"{base_url}/chat/completions",
            api_key=api_key,
            http_client=httpx.Client(timeout=120),
        )
    
    def chat(self, messages: List[Dict], **kwargs) -> Dict[str, Any]:
        """发送聊天请求"""
        try:
            response = self.client.chat.completions.create(
                model=self.model,
                messages=messages,
                **kwargs
            )
            return {
                'success': True,
                'content': response.choices[0].message.content,
                'model': response.model,
                'usage': {
                    'prompt_tokens': response.usage.prompt_tokens,
                    'completion_tokens': response.usage.completion_tokens,
                }
            }
        except Exception as e:
            return {
                'success': False,
                'error': str(e),
                'provider': self.name,
            }
    
    def is_available(self) -> bool:
        """检查API Key是否有效"""
        try:
            response = self.client.chat.completions.create(
                model=self.model,
                messages=[{"role": "user", "content": "hi"}],
                max_tokens=1,
            )
            return True
        except Exception:
            return False


class ProviderPool:
    """提供商池 - 支持多key轮转、自动降级"""
    
    def __init__(self):
        self.providers: List[Provider] = []
        self._loaded = False

    def _load_from_config(self):
        """从配置文件加载提供商"""
        if self._loaded:
            return
        self._loaded = True
        try:
            from prism.config import config
        except Exception:
            return
        
        # 主提供商
        default_model = config.get('model.default', 'gpt-4o')
        provider_name = config.get('model.provider', 'openai')
        base_url = config.get('model.base_url', 'https://api.openai.com/v1')
        api_key = config.get('model.api_key', '') or os.getenv(f'{provider_name.upper()}_API_KEY', '') or config.get(f'providers.{provider_name}.api_key', '')
        
        if api_key:
            self.providers.append(OpenAIProvider(
                name=provider_name,
                base_url=base_url,
                api_key=api_key,
                model=default_model,
            ))
        
        # 备用提供商
        fallback_chain = config.get('fallback.chain', [])
        for fallback in fallback_chain:
            # 解析格式: "provider/model" 或 "model"
            if '/' in fallback:
                p_name, model = fallback.split('/', 1)
            else:
                p_name = 'openai'
                model = fallback
            
            # 从环境变量或配置中获取key
            env_key = f"{p_name.upper()}_API_KEY"
            key = os.getenv(env_key) or config.get(f'providers.{p_name}.api_key', '')
            url = config.get(f'providers.{p_name}.base_url', 'https://api.openai.com/v1')
            
            if key:
                self.providers.append(OpenAIProvider(
                    name=p_name,
                    base_url=url,
                    api_key=key,
                    model=model,
                ))
    
    def chat(self, messages: List[Dict], **kwargs) -> Dict[str, Any]:
        """发送请求，自动降级"""
        self._load_from_config()
        
        if not self.providers:
            return {
                'success': False,
                'error': '未配置可用模型提供商。请先在 ~/.prism/config.yaml 填写 model.api_key，或使用 prism config set model.api_key <你的密钥>。',
            }

        last_error = None
        for provider in self.providers:
            result = provider.chat(messages, **kwargs)
            if result.get('success'):
                return result
            last_error = result.get('error')

        return {
            'success': False,
            'error': last_error or '所有提供商均不可用，请检查网络与 API Key。',
        }
    
    def add_provider(self, provider: Provider):
        """添加提供商"""
        self.providers.append(provider)
    
    def list_providers(self) -> List[str]:
        """列出所有提供商"""
        self._load_from_config()
        return [p.name for p in self.providers]


# 全局提供商池
provider_pool = ProviderPool()
