"""
PRISM Agent - 模型提供商管理
整合多模型、自动降级、凭证池轮转
"""

import logging
import os
import random
import time
from typing import Optional, List, Dict, Any
from abc import ABC, abstractmethod

logger = logging.getLogger("prism.providers")


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
        # 延迟导入：避免 import prism.providers.manager 时强制要求 openai/httpx 已安装
        try:
            from openai import OpenAI
            import httpx
        except ImportError as exc:
            raise ImportError(
                f"OpenAIProvider 需要 openai 和 httpx 依赖，"
                f"请执行 `pip install openai httpx` 或 `uv add openai httpx`。"
            ) from exc
        self.client = OpenAI(
            base_url=base_url,
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

    def stream_chat(self, messages: List[Dict], on_chunk, stop_callback=None, **kwargs) -> Dict[str, Any]:
        """流式聊天请求，逐 chunk 回调"""
        try:
            stream = self.client.chat.completions.create(
                model=self.model,
                messages=messages,
                stream=True,
                **kwargs
            )
            full_content = []
            for chunk in stream:
                if stop_callback and stop_callback():
                    break
                delta = chunk.choices[0].delta if chunk.choices else None
                content = delta.content if delta and delta.content else ''
                if content:
                    full_content.append(content)
                    if on_chunk:
                        on_chunk(content)
            text = ''.join(full_content)
            return {'success': True, 'content': text}
        except Exception as e:
            return {'success': False, 'error': str(e), 'provider': self.name}

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
    """提供商池 - 支持多key轮转、自动降级、MoA多模型投票"""
    
    def __init__(self):
        self.providers: List[Provider] = []
        self._loaded = False

    def _load_from_config(self):
        """从配置文件加载提供商；每次调用前重置加载状态，保证配置变更后即时生效。"""
        self._loaded = False
        if self.providers:
            self.providers = []
        try:
            from prism.config import config as cfg
        except Exception:
            return

        # 主提供商
        default_model = cfg.get('model.default', 'step-3.7-flash')
        provider_name = cfg.get('model.provider', 'stepfun')
        base_url = cfg.get('model.base_url', 'https://api.stepfun.com/step_plan/v1')
        api_key = cfg.get('model.api_key', '') or os.getenv(f'{provider_name.upper()}_API_KEY', '') or cfg.get(f'providers.{provider_name}.api_key', '')

        if api_key:
            self.providers.append(OpenAIProvider(
                name=provider_name,
                base_url=base_url,
                api_key=api_key,
                model=default_model,
            ))

        # 备用提供商
        fallback_chain = cfg.get('fallback.chain', [])
        for fallback in fallback_chain:
            # 解析格式: "provider/model" 或 "model"
            if '/' in fallback:
                p_name, model = fallback.split('/', 1)
            else:
                p_name = 'openai'
                model = fallback

            # 从环境变量或配置中获取key
            env_key = f"{p_name.upper()}_API_KEY"
            key = os.getenv(env_key) or cfg.get(f'providers.{p_name}.api_key', '')
            url = cfg.get(f'providers.{p_name}.base_url', 'https://api.openai.com/v1')

            if key:
                self.providers.append(OpenAIProvider(
                    name=p_name,
                    base_url=url,
                    api_key=key,
                    model=model,
                ))

        # MoA 多模型投票：配置项 moa.ensemble 为模型列表时，为每个模型建 provider
        moa_ensemble = cfg.get('moa.ensemble', []) or []
        moa_base_url = cfg.get('moa.base_url', '') or base_url
        moa_api_key = cfg.get('moa.api_key', '') or api_key
        for model_name in moa_ensemble:
            if not model_name:
                continue
            self.providers.append(OpenAIProvider(
                name=f'moa/{model_name}',
                base_url=moa_base_url,
                api_key=moa_api_key,
                model=model_name,
            ))
    
    def _should_retry(self, exc: Exception) -> bool:
        status = None
        error_str = str(exc)
        for part in error_str.split():
            if part.isdigit():
                candidate = int(part)
                if 100 <= candidate <= 599:
                    status = candidate
                    break
        if status is None:
            return False
        return status in {429, 500, 502, 503, 504}

    def _delay_for_retry(self, attempt: int) -> float:
        return min(1.0 * (2 ** attempt) + random.uniform(0, 0.5), 30.0)

    def _chat_with_retry(self, provider: Provider, messages: List[Dict], max_retries: int = 3, **kwargs) -> Dict[str, Any]:
        last_error = None
        for attempt in range(max_retries):
            try:
                result = provider.chat(messages, **kwargs)
                if result.get('success'):
                    return result
                last_error = result.get('error')
                if last_error and self._should_retry(Exception(last_error)):
                    time.sleep(self._delay_for_retry(attempt))
                    continue
                return result
            except Exception as exc:
                last_error = str(exc)
                if attempt < max_retries - 1 and self._should_retry(exc):
                    time.sleep(self._delay_for_retry(attempt))
                    continue
                return {
                    'success': False,
                    'error': last_error,
                    'provider': getattr(provider, 'name', 'unknown'),
                }
        return {
            'success': False,
            'error': last_error or 'retry exhausted',
            'provider': getattr(provider, 'name', 'unknown'),
        }

    def _stream_with_retry(self, provider: Provider, messages: List[Dict], on_chunk, max_retries: int = 3, **kwargs) -> Dict[str, Any]:
        last_error = None
        for attempt in range(max_retries):
            try:
                result = provider.stream_chat(messages, on_chunk, **kwargs)
                if result.get('success'):
                    return result
                last_error = result.get('error')
                if last_error and self._should_retry(Exception(last_error)):
                    time.sleep(self._delay_for_retry(attempt))
                    continue
                return result
            except Exception as exc:
                last_error = str(exc)
                if attempt < max_retries - 1 and self._should_retry(exc):
                    time.sleep(self._delay_for_retry(attempt))
                    continue
                return {
                    'success': False,
                    'error': last_error,
                    'provider': getattr(provider, 'name', 'unknown'),
                }
        return {
            'success': False,
            'error': last_error or 'retry exhausted',
            'provider': getattr(provider, 'name', 'unknown'),
        }

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
            result = self._chat_with_retry(provider, messages, **kwargs)
            if result.get('success'):
                return result
            last_error = result.get('error')

        return {
            'success': False,
            'error': last_error or '所有提供商均不可用，请检查网络与 API Key。',
        }

    def stream_chat(self, messages: List[Dict], on_chunk, **kwargs) -> Dict[str, Any]:
        """流式请求，自动降级"""
        self._load_from_config()
        
        if not self.providers:
            return {'success': False, 'error': '未配置可用模型提供商。'}
        
        last_error = None
        for provider in self.providers:
            result = self._stream_with_retry(provider, messages, on_chunk, **kwargs)
            if result.get('success'):
                return result
            last_error = result.get('error')
        
        return {'success': False, 'error': last_error or '所有提供商均不可用。'}
    
    def add_provider(self, provider: Provider):
        """添加提供商"""
        self.providers.append(provider)
    
    def list_providers(self) -> List[str]:
        """列出所有提供商"""
        self._load_from_config()
        return [p.name for p in self.providers]

    def set_default_model(self, model: str) -> Dict[str, Any]:
        """运行时切换默认模型；影响已有 provider 实例及配置。"""
        if not model:
            return {'success': False, 'error': 'model is required'}
        try:
            from prism.config import get_config
            get_config().set('model.default', model)
        except Exception as exc:
            return {'success': False, 'error': f'set config failed: {exc}'}
        self._load_from_config()
        updated = 0
        for provider in self.providers:
            if hasattr(provider, 'model'):
                provider.model = model
                updated += 1
        return {'success': True, 'model': model, 'updated_providers': updated}

    def chat_moa(self, messages: List[Dict], aggregate: bool = True, **kwargs) -> Dict[str, Any]:
        """MoA 多模型投票：同时问多个模型，返回多数答案或聚合结果。"""
        self._load_from_config()
        moa_providers = [p for p in self.providers if p.name.startswith('moa/')]
        if not moa_providers:
            return self.chat(messages, **kwargs)

        results: List[Dict[str, Any]] = []
        for provider in moa_providers:
            try:
                result = self._chat_with_retry(provider, messages, **kwargs)
            except Exception as exc:
                result = {'success': False, 'error': str(exc), 'provider': provider.name}
            results.append(result)

        successes = [r for r in results if r.get('success')]
        if not successes:
            return {
                'success': False,
                'error': 'MoA 所有参考模型均不可用。',
                'moa_results': results,
            }

        contents = [r.get('content', '') or '' for r in successes if r.get('content')]
        if not contents:
            return {
                'success': False,
                'error': 'MoA 参考模型未返回有效内容。',
                'moa_results': results,
            }

        if not aggregate:
            return {
                'success': True,
                'content': '\n\n---\n\n'.join(contents),
                'moa_results': results,
                'model': 'moa/ensemble',
            }

        try:
            aggregator_prompt = (
                "以下是多个模型对同一问题的回答，请综合这些回答，"
                "给出一个更准确、全面的最终答案。\n\n"
            )
            for idx, text in enumerate(contents, 1):
                aggregator_prompt += f"### 模型 {idx}\n{text}\n\n"
            aggregator_prompt += "请直接给出最终答案："

            primary = moa_providers[0]
            agg_result = self._chat_with_retry(primary, [{"role": "user", "content": aggregator_prompt}], **kwargs)
            if agg_result.get('success'):
                return {
                    'success': True,
                    'content': agg_result.get('content', ''),
                    'moa_results': results,
                    'model': f"moa/{primary.model}",
                }
        except Exception as exc:
            logger.debug("MoA aggregation failed: %s", exc)

        return {
            'success': True,
            'content': contents[0],
            'moa_results': results,
            'model': moa_providers[0].model,
        }


# 全局提供商池
provider_pool = ProviderPool()
