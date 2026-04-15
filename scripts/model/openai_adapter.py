"""
ADDS Model Layer — OpenAI 兼容 API 适配器

基于 openai 库，支持所有 OpenAI 兼容格式的 API：
- NVIDIA NIM (https://integrate.api.nvidia.com/v1)
- OpenAI 官方
- 其他 OpenAI 兼容端点
"""

import os
from typing import AsyncIterator, Optional

from .base import ModelInterface, ModelResponse


class OpenAIAdapter(ModelInterface):
    """OpenAI 兼容 API 适配器

    使用 openai 库调用任何 OpenAI 兼容格式的 API。
    支持流式输出。
    """

    def __init__(self, provider_config: dict):
        self.base_url = provider_config["base_url"]
        self.api_key_env = provider_config.get("api_key_env", "OPENAI_API_KEY")
        self.api_key = os.environ.get(self.api_key_env, provider_config.get("api_key", ""))
        self.model = provider_config.get("model", "meta/llama-3.1-70b-instruct")
        self.context_window = provider_config.get("context_window", 128000)
        self._features = {
            "streaming": True,
            "tools": True,
            "vision": False,
            "system_prompt": True,
            "thinking": False,
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
                raise ImportError("openai 库未安装。请运行: pip install openai")
        return self._client

    async def chat(
        self,
        messages: list[dict],
        system_prompt: Optional[str] = None,
        tools: Optional[list[dict]] = None,
        stream: bool = True,
        **kwargs,
    ) -> AsyncIterator[ModelResponse]:
        """流式聊天接口（OpenAI 格式）"""
        client = self._get_client()

        # 构建消息列表
        api_messages = []
        if system_prompt:
            api_messages.append({"role": "system", "content": system_prompt})
        for msg in messages:
            role = msg.get("role", "user")
            content = msg.get("content", "")
            if role in ("user", "assistant"):
                api_messages.append({"role": role, "content": content})

        request_params = {
            "model": kwargs.pop("model", self.model),
            "messages": api_messages,
            "max_tokens": kwargs.pop("max_tokens", 4096),
            "stream": stream,
        }
        if tools:
            request_params["tools"] = tools
        request_params.update(kwargs)

        try:
            if stream:
                response = await client.chat.completions.create(**request_params)
                collected = []
                async for chunk in response:
                    delta = chunk.choices[0].delta if chunk.choices else None
                    if delta and delta.content:
                        collected.append(delta.content)
                        yield ModelResponse(
                            content=delta.content,
                            model=self.model,
                            usage={"input_tokens": 0, "output_tokens": 0},
                            finish_reason="streaming",
                        )
                    finish = chunk.choices[0].finish_reason if chunk.choices else None
                    if finish == "stop":
                        yield ModelResponse(
                            content="",
                            model=self.model,
                            usage={"input_tokens": 0, "output_tokens": len(collected)},
                            finish_reason="stop",
                        )
            else:
                request_params["stream"] = False
                response = await client.chat.completions.create(**request_params)
                content = response.choices[0].message.content or ""
                usage = {
                    "input_tokens": getattr(response.usage, "prompt_tokens", 0),
                    "output_tokens": getattr(response.usage, "completion_tokens", 0),
                }
                yield ModelResponse(
                    content=content,
                    model=response.model or self.model,
                    usage=usage,
                    finish_reason="stop",
                )

        except Exception as e:
            yield ModelResponse(
                content=f"API 调用失败: {e}",
                model=self.model,
                usage={"input_tokens": 0, "output_tokens": 0},
                finish_reason="error",
            )

    def count_tokens(self, text: str) -> int:
        cn_chars = sum(1 for c in text if "\u4e00" <= c <= "\u9fff")
        en_chars = len(text) - cn_chars
        return cn_chars // 2 + en_chars // 4

    def get_context_window(self) -> int:
        return self.context_window

    def get_model_name(self) -> str:
        return self.model

    def supports_feature(self, name: str) -> bool:
        return self._features.get(name, False)
