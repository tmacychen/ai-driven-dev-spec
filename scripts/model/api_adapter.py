"""
ADDS Model Layer — API 调用适配器

基于 openai 库，兼容 OpenAI/Anthropic 格式的 HTTP API 调用。
"""

import os
from typing import AsyncIterator, Optional

from .base import ModelInterface, ModelResponse


class APIAdapter(ModelInterface):
    """API 调用适配器 — 基于 openai 库

    支持 OpenAI 兼容格式的 API 调用（MiniMax、DeepSeek 等均兼容）。
    """

    def __init__(self, provider_config: dict):
        self.base_url = provider_config["base_url"]
        self.api_key_env = provider_config.get("api_key_env", "OPENAI_API_KEY")
        self.api_key = os.environ.get(self.api_key_env, provider_config.get("api_key", ""))
        self.model = provider_config.get("model", "gpt-4")
        self.context_window = provider_config.get("context_window", 128000)
        self._features = {
            "streaming": True,
            "tools": True,
            "vision": False,
            "system_prompt": True,
        }
        self._client = None

    def _get_client(self):
        """延迟初始化 openai 客户端"""
        if self._client is None:
            try:
                from openai import AsyncOpenAI

                self._client = AsyncOpenAI(
                    base_url=self.base_url,
                    api_key=self.api_key,
                )
            except ImportError:
                raise ImportError(
                    "openai 库未安装。请运行: pip install openai"
                )
        return self._client

    async def chat(
        self,
        messages: list[dict],
        system_prompt: Optional[str] = None,
        tools: Optional[list[dict]] = None,
        stream: bool = True,
        **kwargs,
    ) -> AsyncIterator[ModelResponse]:
        """流式聊天接口"""
        client = self._get_client()

        # 构建消息列表
        api_messages = []
        if system_prompt:
            api_messages.append({"role": "system", "content": system_prompt})
        api_messages.extend(messages)

        # 构建请求参数
        request_params = {
            "model": kwargs.pop("model", self.model),
            "messages": api_messages,
            "stream": stream,
        }
        if tools:
            request_params["tools"] = tools
        request_params.update(kwargs)

        try:
            if stream:
                response = await client.chat.completions.create(**request_params)
                collected_content = []
                collected_usage = {"input_tokens": 0, "output_tokens": 0}

                async for chunk in response:
                    if chunk.choices:
                        delta = chunk.choices[0].delta
                        if delta.content:
                            collected_content.append(delta.content)
                            yield ModelResponse(
                                content=delta.content,
                                model=chunk.model or self.model,
                                usage=collected_usage,
                                finish_reason="streaming",
                            )
                        # 最后一个 chunk 可能有 usage
                        if hasattr(chunk, "usage") and chunk.usage:
                            collected_usage = {
                                "input_tokens": getattr(chunk.usage, "prompt_tokens", 0) or 0,
                                "output_tokens": getattr(chunk.usage, "completion_tokens", 0) or 0,
                            }

                    # 流结束
                    if chunk.choices and chunk.choices[0].finish_reason:
                        yield ModelResponse(
                            content="",
                            model=chunk.model or self.model,
                            usage=collected_usage,
                            finish_reason=chunk.choices[0].finish_reason,
                        )
            else:
                response = await client.chat.completions.create(**request_params)
                choice = response.choices[0]
                usage_data = {
                    "input_tokens": getattr(response.usage, "prompt_tokens", 0) or 0,
                    "output_tokens": getattr(response.usage, "completion_tokens", 0) or 0,
                }
                yield ModelResponse(
                    content=choice.message.content or "",
                    model=response.model or self.model,
                    usage=usage_data,
                    tool_calls=choice.message.tool_calls,
                    finish_reason=choice.finish_reason or "stop",
                )

        except Exception as e:
            yield ModelResponse(
                content=f"API 调用失败: {e}",
                model=self.model,
                usage={"input_tokens": 0, "output_tokens": 0},
                finish_reason="error",
            )

    def count_tokens(self, text: str) -> int:
        """Token 计数（近似估算）"""
        # 简单估算：英文 ~4 字符/token，中文 ~2 字符/token
        cn_chars = sum(1 for c in text if "\u4e00" <= c <= "\u9fff")
        en_chars = len(text) - cn_chars
        return cn_chars // 2 + en_chars // 4

    def get_context_window(self) -> int:
        """返回模型上下文窗口大小"""
        return self.context_window

    def supports_feature(self, name: str) -> bool:
        """查询模型支持的功能"""
        return self._features.get(name, False)
