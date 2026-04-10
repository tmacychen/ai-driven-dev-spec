"""
ADDS Model Layer — API 调用适配器

基于 anthropic 库，使用 Anthropic 兼容格式调用 MiniMax 等模型。
优势：原生支持 thinking 块，可获取模型推理过程。
"""

import os
from typing import AsyncIterator, Optional

from .base import ModelInterface, ModelResponse


class APIAdapter(ModelInterface):
    """API 调用适配器 — 基于 anthropic 库

    支持 Anthropic 兼容格式的 API 调用（MiniMax 官方推荐方式）。
    原生支持 thinking 块，可分离模型推理过程和最终回复。
    """

    def __init__(self, provider_config: dict):
        self.base_url = provider_config["base_url"]
        self.api_key_env = provider_config.get("api_key_env", "ANTHROPIC_API_KEY")
        self.api_key = os.environ.get(self.api_key_env, provider_config.get("api_key", ""))
        self.model = provider_config.get("model", "MiniMax-M2.7")
        self.context_window = provider_config.get("context_window", 204800)
        self.thinking_budget = provider_config.get("thinking_budget", 10000)
        self._features = {
            "streaming": True,
            "tools": True,
            "vision": False,
            "system_prompt": True,
            "thinking": True,  # 支持 thinking 块
        }
        self._client = None

    def _get_client(self):
        """延迟初始化 anthropic 客户端"""
        if self._client is None:
            try:
                from anthropic import AsyncAnthropic

                self._client = AsyncAnthropic(
                    base_url=self.base_url,
                    api_key=self.api_key,
                )
            except ImportError:
                raise ImportError(
                    "anthropic 库未安装。请运行: pip install anthropic"
                )
        return self._client

    def _build_anthropic_messages(self, messages: list[dict]) -> list[dict]:
        """将 OpenAI 格式消息转为 Anthropic 格式

        OpenAI: [{"role": "system", "content": "..."}, {"role": "user", "content": "..."}]
        Anthropic: system 单独传, messages 只含 user/assistant
        """
        result = []
        for msg in messages:
            role = msg.get("role", "user")
            content = msg.get("content", "")
            # 跳过 system 消息（通过 system_prompt 参数单独传）
            if role == "system":
                continue
            # 转换为 Anthropic 格式
            result.append({"role": role, "content": content})
        return result

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

        # 构建消息列表（过滤 system 消息）
        api_messages = self._build_anthropic_messages(messages)

        # 构建请求参数
        request_params = {
            "model": kwargs.pop("model", self.model),
            "max_tokens": kwargs.pop("max_tokens", 16384),
            "messages": api_messages,
        }

        # 系统提示词（Anthropic 格式：单独传）
        if system_prompt:
            request_params["system"] = system_prompt

        # 启用 thinking（extended thinking）
        # MiniMax-M2.x 支持推理过程输出
        request_params["thinking"] = {
            "type": "enabled",
            "budget_tokens": self.thinking_budget,
        }

        # 工具定义
        if tools:
            request_params["tools"] = tools

        request_params.update(kwargs)

        try:
            if stream:
                # 流式调用
                async with client.messages.stream(**request_params) as stream_ctx:
                    collected_content = []
                    collected_thinking = []
                    collected_usage = {"input_tokens": 0, "output_tokens": 0}

                    async for event in stream_ctx:
                        # 处理 thinking 事件
                        if event.type == "content_block_delta":
                            delta = event.delta
                            if hasattr(delta, "thinking") and delta.thinking:
                                collected_thinking.append(delta.thinking)
                                yield ModelResponse(
                                    content="",
                                    model=request_params["model"],
                                    usage=collected_usage,
                                    finish_reason="thinking",
                                    thinking=delta.thinking,
                                )
                            elif hasattr(delta, "text") and delta.text:
                                collected_content.append(delta.text)
                                yield ModelResponse(
                                    content=delta.text,
                                    model=request_params["model"],
                                    usage=collected_usage,
                                    finish_reason="streaming",
                                )

                        # 处理 message_stop 事件
                        elif event.type == "message_stop":
                            # 获取最终 usage
                            msg = await stream_ctx.get_final_message()
                            collected_usage = {
                                "input_tokens": getattr(msg.usage, "input_tokens", 0),
                                "output_tokens": getattr(msg.usage, "output_tokens", 0),
                            }
                            yield ModelResponse(
                                content="",
                                model=msg.model or self.model,
                                usage=collected_usage,
                                finish_reason="stop",
                                thinking="".join(collected_thinking) or None,
                            )

            else:
                # 非流式调用
                response = await client.messages.create(**request_params)

                # 提取 thinking 和 text 内容
                thinking_text = ""
                response_text = ""
                for block in response.content:
                    if block.type == "thinking":
                        thinking_text += block.thinking
                    elif block.type == "text":
                        response_text += block.text

                usage_data = {
                    "input_tokens": getattr(response.usage, "input_tokens", 0),
                    "output_tokens": getattr(response.usage, "output_tokens", 0),
                }

                yield ModelResponse(
                    content=response_text,
                    model=response.model or self.model,
                    usage=usage_data,
                    finish_reason=response.stop_reason or "stop",
                    thinking=thinking_text or None,
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
        cn_chars = sum(1 for c in text if "\u4e00" <= c <= "\u9fff")
        en_chars = len(text) - cn_chars
        return cn_chars // 2 + en_chars // 4

    def get_context_window(self) -> int:
        """返回模型上下文窗口大小"""
        return self.context_window

    def supports_feature(self, name: str) -> bool:
        """查询模型支持的功能"""
        return self._features.get(name, False)
