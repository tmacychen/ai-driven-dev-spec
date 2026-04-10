#!/usr/bin/env python3
"""
ADDS Agent Loop — Rich 美化版

核心能力：创建 agent → 注入系统提示词 → 调用大模型 → 交互对话
使用 Rich 库实现彩色终端输出、思考过程面板、响应面板等。
"""

import asyncio
from dataclasses import dataclass, field
from typing import Optional, List, Dict, Any

from model.base import ModelInterface

# prompt_toolkit 用于处理中文输入的退格问题
try:
    from prompt_toolkit import PromptSession
    from prompt_toolkit.formatted_text import HTML
    HAS_PT = True
except ImportError:
    HAS_PT = False


@dataclass
class AgentSession:
    """Agent 会话状态"""
    system_prompt: str = ""
    messages: List[Dict[str, Any]] = field(default_factory=list)
    turn_count: int = 0


class AgentLoop:
    """
    Agent Loop — Rich 美化版

    流程：
    1. 注入 system_prompt
    2. 用户输入 → 模型响应 → Rich 渲染
    3. 循环直到用户退出
    """

    def __init__(self, model: ModelInterface, system_prompt: str = "",
                 console=None, skin=None):
        self.model = model
        self.session = AgentSession(system_prompt=system_prompt)
        self.console = console
        self.skin = skin

        # 如果没有传入 console/skin，使用简单模式
        if self.console is None:
            try:
                from skins import create_console, SkinConfig
                self.console = create_console()
                self.skin = SkinConfig({})
            except ImportError:
                self.console = None
                self.skin = None

        # prompt_toolkit session（用于 async prompt）
        self._pt_session = PromptSession() if HAS_PT else None

    def _print(self, *args, **kwargs):
        """兼容 Rich 和普通 print"""
        if self.console:
            self.console.print(*args, **kwargs)
        else:
            # 去除 Rich markup
            import re
            msg = " ".join(str(a) for a in args)
            msg = re.sub(r'\[/?[^\]]*\]', '', msg)
            print(msg, **kwargs)

    async def run(self):
        """主循环：交互式对话"""
        model_name = self.model.get_model_name()
        ctx_window = self.model.get_context_window()

        # 获取皮肤颜色
        accent = self.skin.color("ui_accent") if self.skin else "#FFBF00"
        text = self.skin.color("banner_text") if self.skin else "#FFF8DC"
        dim = self.skin.color("banner_dim") if self.skin else "#B8860B"
        label = self.skin.color("ui_label") if self.skin else "#4dd0e1"
        prompt_color = self.skin.color("prompt") if self.skin else "#FFF8DC"
        prompt_symbol = self.skin.prompt_symbol if self.skin else "❯"

        self._print(f"[bold {accent}]🤖 Agent 已启动[/]")
        self._print(f"  [{label}]模型:[/] [{text}]{model_name}[/]")
        self._print(f"  [{label}]上下文:[/] [{text}]{ctx_window:,} tokens[/]")
        if self.session.system_prompt:
            sp = self.session.system_prompt[:80]
            self._print(f"  [{label}]角色设定:[/] [{text}]{sp}[/]")
        self._print(f"\n[dim {dim}]💡 输入消息开始对话，输入 /quit 或 Ctrl+C 退出[/]\n")

        while True:
            try:
                # 使用 prompt_toolkit async 版本解决中文退格问题
                if self.console:
                    if self._pt_session:
                        prompt_str = HTML(f'<style fg="{prompt_color}">{prompt_symbol}</style> ')
                        user_input = (await self._pt_session.prompt_async(prompt_str)).strip()
                    else:
                        self.console.print(f"[{prompt_color}]{prompt_symbol}[/] ", end="")
                        user_input = input().strip()
                else:
                    user_input = input("你> ").strip()
            except (EOFError, KeyboardInterrupt):
                self._print("\n\n[bold]👋 再见！[/]")
                break

            if not user_input:
                continue
            if user_input.lower() in ("/quit", "/exit", "/q"):
                goodbye = self.skin.branding("goodbye", "Goodbye!") if self.skin else "再见！"
                self._print(f"[bold]{goodbye}[/]")
                break

            # 追加用户消息
            self.session.messages.append({"role": "user", "content": user_input})
            self.session.turn_count += 1

            # 调用模型
            full_response = []
            thinking_text = ""
            thinking_shown = False
            is_streaming = False

            try:
                async for resp in self.model.chat(
                    self.session.messages,
                    system_prompt=self.session.system_prompt or None,
                    stream=True,
                ):
                    if resp.finish_reason == "error":
                        error_color = self.skin.color("ui_error", "#ef5350") if self.skin else "#ef5350"
                        self._print(f"[bold {error_color}]❌ {resp.content}[/]")
                        break

                    # 收集思考过程
                    if resp.thinking and resp.finish_reason == "thinking":
                        thinking_text += resp.thinking
                        if not thinking_shown:
                            dim_c = self.skin.color("banner_dim") if self.skin else "#B8860B"
                            self._print(f"[dim {dim_c}]🧠 思考中...[/]", end="")
                            thinking_shown = True

                    # 流式回复内容
                    if resp.content and resp.finish_reason == "streaming":
                        is_streaming = True
                        if thinking_shown:
                            self._print()
                            thinking_shown = False
                        print(resp.content, end="", flush=True)
                        full_response.append(resp.content)

                    # 非流式一次性响应（CLI 适配器等）
                    if resp.finish_reason == "stop":
                        if resp.thinking:
                            thinking_text = resp.thinking
                        if resp.content:
                            full_response.append(resp.content)

                # 响应渲染
                assistant_content = "".join(full_response)
                if assistant_content:
                    self.session.messages.append({"role": "assistant", "content": assistant_content})

                    if self.console and not is_streaming:
                        # 非流式：用面板渲染
                        border = self.skin.color("response_border") if self.skin else "#FFD700"
                        response_label = self.skin.branding("response_label", " ⚡ ADDS ") if self.skin else " ⚡ ADDS "
                        from rich.panel import Panel
                        panel = Panel(
                            assistant_content,
                            title=f"[{border}]{response_label}[/]",
                            border_style=border,
                            padding=(0, 1),
                        )
                        self.console.print(panel)
                    elif is_streaming:
                        print()  # 流式打印完换行

                # 思考过程显示（放在响应后）
                if thinking_text and self.console:
                    dim_c = self.skin.color("banner_dim") if self.skin else "#B8860B"
                    short = thinking_text[:200] + ("..." if len(thinking_text) > 200 else "")
                    self._print(f"[dim {dim_c}]🧠 {short}[/]")

            except Exception as e:
                error_color = self.skin.color("ui_error", "#ef5350") if self.skin else "#ef5350"
                self._print(f"[bold {error_color}]❌ 调用失败: {e}[/]")

            self._print()  # 空行分隔

        return self.session.turn_count
