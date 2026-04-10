"""
ADDS Model Layer — 大模型调用层

支持三种调用模式：
- API: 直接 HTTP 调用（OpenAI/Anthropic 兼容）
- CLI: 任务派发协议（mmx, codebuddy 等 CLI 工具）
- SDK: 直接编程调用（codebuddy-agent-sdk）
"""

from .base import ModelInterface, ModelResponse
from .factory import ModelFactory
from .api_adapter import APIAdapter
from .cli_adapter import CLIAdapter
from .sdk_adapter import SDKAdapter
from .task_dispatcher import TaskDispatcher, CLIProfile

__all__ = [
    "ModelInterface",
    "ModelResponse",
    "ModelFactory",
    "APIAdapter",
    "CLIAdapter",
    "SDKAdapter",
    "TaskDispatcher",
    "CLIProfile",
]
