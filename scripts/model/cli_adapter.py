"""
ADDS Model Layer — CLI 工具适配器

基于 subprocess + CLIProfile 的 CLI 工具调用适配器。
支持 mmx、codebuddy 等 CLI 工具。
"""

import shutil
from typing import AsyncIterator, Optional

from .base import ModelInterface, ModelResponse
from .task_dispatcher import CLIProfile, TaskDispatcher


class CLIAdapter(ModelInterface):
    """CLI 工具适配器 — 基于 subprocess + CLIProfile

    将 CLI 工具的调用封装为 ModelInterface 接口，
    通过 TaskDispatcher 统一派发任务。
    """

    def __init__(self, cli_config: dict):
        self.profile: CLIProfile = cli_config["profile"]
        self.model = cli_config.get("model", self.profile.name)
        self.context_window = cli_config.get("context_window", 204800)
        self.dispatcher = TaskDispatcher(self.profile)

        self._features = {
            "streaming": self.profile.dispatch.get("stream_supported", True),
            "tools": False,  # CLI 工具一般不支持 function calling
            "vision": False,
            "system_prompt": self.profile.dispatch.get("system_prompt_method") is not None,
        }

    async def chat(
        self,
        messages: list[dict],
        system_prompt: Optional[str] = None,
        tools: Optional[list[dict]] = None,
        stream: bool = True,
        **kwargs,
    ) -> AsyncIterator[ModelResponse]:
        """聊天接口 — 通过 CLI 工具执行

        将消息列表合并为 prompt，调用 TaskDispatcher 执行。
        """
        # 将消息列表合并为单个 prompt
        prompt_parts = []
        for msg in messages:
            role = msg.get("role", "user")
            content = msg.get("content", "")
            if role == "system":
                prompt_parts.append(f"[System] {content}")
            elif role == "assistant":
                prompt_parts.append(f"[Assistant] {content}")
            else:
                prompt_parts.append(content)

        prompt = "\n".join(prompt_parts)

        # 如果有多轮对话且 profile 支持多轮
        if len(messages) > 1 and self.profile.name == "minimax":
            # mmx 支持多轮 --message 格式
            prompt = self._format_mmx_messages(messages)

        # 确定输出格式
        output_format = kwargs.pop("output_format", self.profile.dispatch.get("output_format", "json"))

        # 派发任务
        response = await self.dispatcher.dispatch(
            prompt=prompt,
            system_prompt=system_prompt,
            output_format=output_format,
            resume_session=kwargs.pop("resume_session", None),
            bypass_permissions=kwargs.pop("bypass_permissions", False),
            extra_args=kwargs.pop("extra_args", None),
        )

        yield response

    def _format_mmx_messages(self, messages: list[dict]) -> str:
        """为 mmx CLI 格式化多轮消息"""
        parts = []
        for msg in messages:
            role = msg.get("role", "user")
            content = msg.get("content", "")
            parts.append(f"{role}:{content}")
        return "\n".join(parts)

    def count_tokens(self, text: str) -> int:
        """Token 计数（近似估算）"""
        cn_chars = sum(1 for c in text if "\u4e00" <= c <= "\u9fff")
        en_chars = len(text) - cn_chars
        return cn_chars // 2 + en_chars // 4

    def get_context_window(self) -> int:
        """返回模型上下文窗口大小"""
        return self.context_window

    def supports_feature(self, name: str) -> bool:
        """查询模型支持的功能"""
        return self._features.get(name, False)

    def is_available(self) -> bool:
        """检查 CLI 工具是否已安装"""
        return shutil.which(self.profile.command) is not None
