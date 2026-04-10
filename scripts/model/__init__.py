"""
ADDS Model Layer — 大模型调用层

支持三种调用模式：
- API: 直接 HTTP 调用（Anthropic 兼容）
- CLI: 命令行工具（mmx, codebuddy）
- SDK: 直接编程调用（codebuddy-agent-sdk）
"""

from .base import ModelInterface, ModelResponse
from .factory import ModelFactory
from .api_adapter import APIAdapter
from .cli_adapter import CLIAdapter
from .sdk_adapter import SDKAdapter

__all__ = [
    "ModelInterface",
    "ModelResponse",
    "ModelFactory",
    "APIAdapter",
    "CLIAdapter",
    "SDKAdapter",
]
