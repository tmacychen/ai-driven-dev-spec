"""
ADDS Model Layer — Provider 包

包含所有支持的模型 Provider 配置。
"""

from .minimax import MINIMAX_PROVIDER
from .codebuddy import CODEBUDDY_PROVIDER
from .registry import ProviderRegistry, get_registry

__all__ = [
    "MINIMAX_PROVIDER",
    "CODEBUDDY_PROVIDER",
    "ProviderRegistry",
    "get_registry",
]
