"""
ADDS Model Layer — SDK 适配器

基于 codebuddy-agent-sdk 的直接编程调用适配器。
"""

from typing import AsyncIterator, Optional

from .base import ModelInterface, ModelResponse


class SDKAdapter(ModelInterface):
    """SDK 适配器 — 直接编程调用（如 codebuddy-agent-sdk）

    与 CLI 适配器不同，SDK 模式直接在进程内调用，
    无需 subprocess 开销，支持更细粒度的控制。
    """

    def __init__(self, sdk_config: dict):
        self.package = sdk_config["package"]  # e.g. "codebuddy-agent-sdk"
        self.model = sdk_config.get("model", "default")
        self.context_window = sdk_config.get("context_window", 200000)
        self._sdk_config = sdk_config
        self._sdk = None

        self._features = {
            "streaming": True,
            "tools": True,
            "vision": False,
            "system_prompt": True,
        }

    def _get_sdk(self):
        """延迟加载 SDK"""
        if self._sdk is None:
            try:
                import importlib
                module_name = self.package.replace("-", "_")
                self._sdk = importlib.import_module(module_name)
            except ImportError:
                raise ImportError(
                    f"{self.package} 未安装。请运行: pip install {self.package}"
                )
        return self._sdk

    async def chat(
        self,
        messages: list[dict],
        system_prompt: Optional[str] = None,
        tools: Optional[list[dict]] = None,
        stream: bool = True,
        **kwargs,
    ) -> AsyncIterator[ModelResponse]:
        """流式聊天接口 — 通过 SDK 调用

        目前支持 codebuddy-agent-sdk。
        """
        sdk = self._get_sdk()

        # 构建 prompt
        prompt_parts = []
        for msg in messages:
            role = msg.get("role", "user")
            content = msg.get("content", "")
            if role != "system":
                prompt_parts.append(content)
        prompt = "\n".join(prompt_parts)

        # 配置选项
        options_kwargs = {
            "permission_mode": kwargs.pop("permission_mode", "bypassPermissions"),
            "max_turns": kwargs.pop("max_turns", 10),
        }
        if self._sdk_config.get("cwd"):
            options_kwargs["cwd"] = self._sdk_config["cwd"]

        try:
            # 使用 codebuddy-agent-sdk 的 query 接口
            if hasattr(sdk, "query"):
                # 构建 options
                options_cls = getattr(sdk, "CodeBuddyAgentOptions", None)
                if options_cls:
                    options = options_cls(**options_kwargs)
                else:
                    options = None

                # 构建 query 参数
                query_kwargs = {"prompt": prompt, "options": options} if options else {"prompt": prompt}

                # 注入 system prompt
                if system_prompt:
                    # codebuddy SDK 通过 options 注入
                    if options and hasattr(options, "system_prompt"):
                        options.system_prompt = system_prompt

                collected_content = []

                async for message in sdk.query(**query_kwargs):
                    # 处理 AssistantMessage
                    if hasattr(message, "content"):
                        for block in message.content:
                            # TextBlock
                            if hasattr(block, "text"):
                                collected_content.append(block.text)
                                yield ModelResponse(
                                    content=block.text,
                                    model=self.model,
                                    usage={"input_tokens": 0, "output_tokens": len(block.text) // 4},
                                    finish_reason="streaming",
                                )
                            # ToolUseBlock
                            elif hasattr(block, "name"):
                                yield ModelResponse(
                                    content="",
                                    model=self.model,
                                    usage={"input_tokens": 0, "output_tokens": 0},
                                    tool_calls=[{"name": block.name, "input": getattr(block, "input", {})}],
                                    finish_reason="tool_use",
                                )

                # 最终响应
                full_content = "".join(collected_content)
                yield ModelResponse(
                    content="",
                    model=self.model,
                    usage={
                        "input_tokens": 0,
                        "output_tokens": max(1, len(full_content) // 4),
                    },
                    finish_reason="stop",
                )
            else:
                yield ModelResponse(
                    content=f"SDK 不支持 query 接口: {self.package}",
                    model=self.model,
                    finish_reason="error",
                )

        except ImportError as e:
            yield ModelResponse(
                content=f"SDK 加载失败: {e}",
                model=self.model,
                finish_reason="error",
            )
        except Exception as e:
            yield ModelResponse(
                content=f"SDK 调用失败: {e}",
                model=self.model,
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

    def is_available(self) -> bool:
        """检查 SDK 是否已安装"""
        try:
            import importlib
            module_name = self.package.replace("-", "_")
            importlib.import_module(module_name)
            return True
        except ImportError:
            return False
