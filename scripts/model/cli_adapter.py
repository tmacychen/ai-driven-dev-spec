"""
ADDS Model Layer — CLI 工具适配器

基于 subprocess 调用 mmx / codebuddy 等 CLI 工具。
支持流式和非流式输出。
"""

import asyncio
import json
import shutil
from typing import AsyncIterator, Optional

from .base import ModelInterface, ModelResponse


class CLIAdapter(ModelInterface):
    """CLI 工具适配器

    支持的 CLI 工具：
    - mmx (MiniMax CLI): mmx text chat --message ... --output json
    - codebuddy: codebuddy -p --output-format json
    """

    def __init__(self, cli_config: dict):
        self.cli_type = cli_config.get("cli_type", "generic")
        self.command = cli_config.get("command", "")
        self.model = cli_config.get("model", "")
        self.context_window = cli_config.get("context_window", 204800)
        self._features = {
            "streaming": True,
            "tools": False,
            "vision": False,
            "system_prompt": True,
            "thinking": self.cli_type == "mmx",
        }

    async def chat(
        self,
        messages: list[dict],
        system_prompt: Optional[str] = None,
        tools: Optional[list[dict]] = None,
        stream: bool = True,
        **kwargs,
    ) -> AsyncIterator[ModelResponse]:
        """聊天接口 — 通过 CLI 工具执行"""
        if self.cli_type == "mmx":
            async for resp in self._chat_mmx(messages, system_prompt, stream, **kwargs):
                yield resp
        elif self.cli_type == "codebuddy":
            async for resp in self._chat_codebuddy(messages, system_prompt, stream, **kwargs):
                yield resp
        else:
            yield ModelResponse(
                content=f"不支持的 CLI 类型: {self.cli_type}",
                model=self.model,
                usage={"input_tokens": 0, "output_tokens": 0},
                finish_reason="error",
            )

    # ─── mmx (MiniMax CLI) ──────────────────────────────────────

    async def _chat_mmx(
        self,
        messages: list[dict],
        system_prompt: Optional[str] = None,
        stream: bool = True,
        **kwargs,
    ) -> AsyncIterator[ModelResponse]:
        """调用 mmx text chat"""
        # 构建命令
        cmd = ["mmx", "text", "chat", "--output", "json"]

        # 添加 model
        if self.model:
            cmd.extend(["--model", self.model])

        # 添加 system prompt
        if system_prompt:
            cmd.extend(["--system", system_prompt])

        # 添加消息
        for msg in messages:
            role = msg.get("role", "user")
            content = msg.get("content", "")
            if role == "system":
                # system 消息通过 --system 传递，跳过
                continue
            elif role == "assistant":
                cmd.extend(["--message", f"assistant:{content}"])
            else:
                cmd.extend(["--message", content])

        # 执行
        try:
            proc = await asyncio.create_subprocess_exec(
                *cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            stdout, stderr = await asyncio.wait_for(
                proc.communicate(), timeout=120
            )

            if proc.returncode != 0:
                err = stderr.decode(errors="replace").strip()
                yield ModelResponse(
                    content=f"mmx 调用失败 (exit {proc.returncode}): {err[:500]}",
                    model=self.model,
                    usage={"input_tokens": 0, "output_tokens": 0},
                    finish_reason="error",
                )
                return

            # 解析 JSON 输出
            raw = stdout.decode(errors="replace").strip()
            data = json.loads(raw)

            # 提取 thinking + text
            thinking_text = ""
            response_text = ""
            for block in data.get("content", []):
                if block.get("type") == "thinking":
                    thinking_text += block.get("thinking", "")
                elif block.get("type") == "text":
                    response_text += block.get("text", "")

            usage = data.get("usage", {})
            yield ModelResponse(
                content=response_text,
                model=data.get("model", self.model),
                usage={
                    "input_tokens": usage.get("input_tokens", 0),
                    "output_tokens": usage.get("output_tokens", 0),
                },
                finish_reason="stop",
                thinking=thinking_text or None,
            )

        except json.JSONDecodeError:
            yield ModelResponse(
                content=raw if 'raw' in dir() else "mmx 返回了非 JSON 格式",
                model=self.model,
                usage={"input_tokens": 0, "output_tokens": 0},
                finish_reason="error",
            )
        except asyncio.TimeoutError:
            yield ModelResponse(
                content="mmx 调用超时 (120s)",
                model=self.model,
                usage={"input_tokens": 0, "output_tokens": 0},
                finish_reason="error",
            )
        except Exception as e:
            yield ModelResponse(
                content=f"mmx 调用异常: {e}",
                model=self.model,
                usage={"input_tokens": 0, "output_tokens": 0},
                finish_reason="error",
            )

    # ─── codebuddy CLI ──────────────────────────────────────────

    async def _chat_codebuddy(
        self,
        messages: list[dict],
        system_prompt: Optional[str] = None,
        stream: bool = True,
        **kwargs,
    ) -> AsyncIterator[ModelResponse]:
        """调用 codebuddy -p"""
        # 构建命令
        cmd = ["codebuddy", "-p", "--output-format", "json", "--tools", ""]

        # codebuddy 不支持 --system-prompt-file，通过消息前缀注入
        prompt_parts = []
        if system_prompt:
            prompt_parts.append(f"[System Instructions] {system_prompt}\n")

        # 合并消息
        for msg in messages:
            role = msg.get("role", "user")
            content = msg.get("content", "")
            if role == "assistant":
                prompt_parts.append(f"[Assistant] {content}")
            else:
                prompt_parts.append(content)

        prompt = "\n".join(prompt_parts)
        cmd.append(prompt)

        # 执行
        try:
            proc = await asyncio.create_subprocess_exec(
                *cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            stdout, stderr = await asyncio.wait_for(
                proc.communicate(), timeout=300
            )

            if proc.returncode != 0:
                err = stderr.decode(errors="replace").strip()
                yield ModelResponse(
                    content=f"codebuddy 调用失败 (exit {proc.returncode}): {err[:500]}",
                    model=self.model,
                    usage={"input_tokens": 0, "output_tokens": 0},
                    finish_reason="error",
                )
                return

            # 解析 JSON 输出（codebuddy 返回 JSON 数组）
            raw = stdout.decode(errors="replace").strip()
            response_text = ""
            thinking_text = ""

            try:
                data = json.loads(raw)
                if isinstance(data, list):
                    # codebuddy 返回完整对话记录，提取所有 assistant 的 output_text
                    for item in data:
                        if item.get("role") == "assistant" and item.get("type") == "message":
                            for block in item.get("content", []):
                                if block.get("type") == "output_text":
                                    response_text += block.get("text", "")
                        # 提取 reasoning
                        if item.get("type") == "reasoning":
                            for block in item.get("rawContent", []):
                                if block.get("type") == "reasoning_text":
                                    thinking_text += block.get("text", "")
                elif isinstance(data, dict):
                    for block in data.get("content", []):
                        if block.get("type") in ("text", "output_text"):
                            response_text += block.get("text", "")
            except json.JSONDecodeError:
                # 非 JSON，直接用文本
                response_text = raw

            yield ModelResponse(
                content=response_text,
                model="codebuddy",
                usage={"input_tokens": 0, "output_tokens": max(1, len(response_text) // 4)},
                finish_reason="stop",
                thinking=thinking_text or None,
            )

        except asyncio.TimeoutError:
            yield ModelResponse(
                content="codebuddy 调用超时 (300s)",
                model=self.model,
                usage={"input_tokens": 0, "output_tokens": 0},
                finish_reason="error",
            )
        except Exception as e:
            yield ModelResponse(
                content=f"codebuddy 调用异常: {e}",
                model=self.model,
                usage={"input_tokens": 0, "output_tokens": 0},
                finish_reason="error",
            )

    # ─── 通用接口 ───────────────────────────────────────────────

    def count_tokens(self, text: str) -> int:
        cn_chars = sum(1 for c in text if "\u4e00" <= c <= "\u9fff")
        en_chars = len(text) - cn_chars
        return cn_chars // 2 + en_chars // 4

    def get_context_window(self) -> int:
        return self.context_window

    def supports_feature(self, name: str) -> bool:
        return self._features.get(name, False)

    def is_available(self) -> bool:
        """检查 CLI 工具是否已安装"""
        return shutil.which(self.command) is not None
