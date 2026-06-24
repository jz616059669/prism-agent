"""
PRISM Agent - 凭证池
支持多 Key 轮转
"""

from typing import Dict, List, Optional


class CredentialPool:
    """
    凭证池
    按策略轮转 api_key
    """

    def __init__(self, provider_name: str, credentials: List[Dict[str, str]]):
        self.provider_name = provider_name
        self.credentials = credentials or []
        self._index = 0

    def next(self) -> Optional[Dict[str, str]]:
        if not self.credentials:
            return None
        cred = self.credentials[self._index % len(self.credentials)]
        self._index += 1
        return cred


__all__ = ['CredentialPool']
