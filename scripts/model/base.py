"""
ADDS Model Layer — 抽象基类与通用数据结构

核心接口：
- ModelResponse: 统一模型响应
- ModelInterface: 模型调用抽象基类（所有 Adapter 必须实现）
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import AsyncIterator, Optional


@dataclass
class ModelResponse:
    """统一模型响应"""

    content: str
    model: str
    usage: dict = field(default_factory=lambda: {"input_tokens": 0, "output_tokens": 0})
    tool_calls: Optional[list] = None
    finish_reason: str = "stop"
    progress_hints: Optional[list[dict]] = None
    # progress_hints 示例:
    # [{"phase": "compiling", "progress": 30, "detail": "Building contracts..."},
    #  {"phase": "testing", "progress": 80, "detail": "Running test suite..."}]


class ModelInterface(ABC):
    """模型调用抽象基类

    所有模型适配器（API / CLI / SDK）必须实现此接口。
    Agent Loop 通过此接口与模型交互，无需关心底层实现。
    """

    @abstractmethod
    async def chat(
        self,
        messages: list[dict],
        system_prompt: Optional[str] = None,
        tools: Optional[list[dict]] = None,
        stream: bool = True,
        **kwargs,
    ) -> AsyncIterator[ModelResponse]:
        """流式聊天接口

        Args:
            messages: 消息列表，格式: [{"role": "user"/"assistant", "content": "..."}]
            system_prompt: 系统提示词（可选，部分 Adapter 通过其他方式注入）
            tools: 工具定义列表（可选）
            stream: 是否启用流式输出
            **kwargs: 模型特定参数

        Yields:
            ModelResponse: 流式响应片段
        """
        pass
        # 让 yield 使其成为异步生成器
        # pylint: disable=unreachable
        yield  # type: ignore  # noqa

    @abstractmethod
    def count_tokens(self, text: str) -> int:
        """Token 计数（近似估算）

        简单估算规则：英文 ~4 字符/token，中文 ~2 字符/token
        """
        pass

    @abstractmethod
    def get_context_window(self) -> int:
        """返回模型上下文窗口大小（tokens）"""
        pass

    @abstractmethod
    def supports_feature(self, name: str) -> bool:
        """查询模型支持的功能

        常见功能名:
        - "streaming": 流式输出
        - "tools": 工具调用
        - "vision": 图像理解
        - "system_prompt": 系统提示词
        """
        pass

    def get_model_name(self) -> str:
        """返回当前使用的模型名称"""
        return getattr(self, "model", "unknown")
