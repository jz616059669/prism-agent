"""
PRISM Agent - Gateway 基础模块
避免循环导入
"""

from dataclasses import dataclass, field
from typing import Optional, Callable, Dict, Any
from datetime import datetime

from prism.interfaces import Message, PlatformAdapter


__all__ = ["Message", "PlatformAdapter"]
