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

        # prompt_toolkit session（用于 async prompt，支持多行）
        if HAS_PT:
            from prompt_toolkit.key_binding import KeyBindings
            kb = KeyBindings()

            @kb.add('escape', 'enter')
            @kb.add('c-j')  # Ctrl+J (Shift+Enter on some terminals)
            def _(event):
                """插入换行而非提交"""
                event.current_buffer.insert_text('\n')

            self._pt_session = PromptSession(
                multiline=False,
                key_bindings=kb,
                enable_open_in_editor=True,  # Ctrl+X Ctrl+E 打开编辑器
            )
        else:
            self._pt_session = None

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
                        user_input = (await self._pt_session.prompt_async(
                            prompt_str,
                            multiline=False,
                            prompt_continuation=HTML(f'<style fg="{dim}">... </style> '),
                        )).strip()
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

            # 命令处理
            cmd = user_input.lower().split()[0]
            if cmd in ("/quit", "/exit", "/q"):
                goodbye = self.skin.branding("goodbye", "Goodbye!") if self.skin else "再见！"
                self._print(f"[bold]{goodbye}[/]")
                break
            elif cmd == "/help":
                help_header = self.skin.branding("help_header", "Available Commands") if self.skin else "Available Commands"
                self._print(f"\n[bold {accent}]{help_header}[/]")
                commands = [
                    ("/help", "显示此帮助信息"),
                    ("/quit, /exit, /q", "退出对话"),
                    ("/clear", "清空对话历史"),
                    ("/history", "查看对话历史摘要"),
                    ("/model", "显示当前模型信息"),
                    ("Ctrl+X Ctrl+E", "打开编辑器编辑多行输入"),
                    ("Esc+Enter", "插入换行（多行输入）"),
                ]
                for name, desc in commands:
                    self._print(f"  [{label}]{name:25}[/] [{text}]{desc}[/]")
                self._print()
                continue
            elif cmd == "/clear":
                self.session.messages.clear()
                self.session.turn_count = 0
                ok_color = self.skin.color("ui_ok", "#4caf50") if self.skin else "#4caf50"
                self._print(f"[{ok_color}]✅ 对话历史已清空[/]\n")
                continue
            elif cmd == "/history":
                if not self.session.messages:
                    self._print(f"[dim {dim}]（暂无对话历史）[/]")
                else:
                    self._print(f"[bold {accent}]📜 对话历史 ({len(self.session.messages)} 条)[/]")
                    for i, msg in enumerate(self.session.messages[-6:]):
                        role = msg["role"]
                        content = msg["content"][:60].replace("\n", " ")
                        role_color = prompt_color if role == "user" else dim
                        self._print(f"  [{role_color}]{role}:[/] [{text}]{content}{'...' if len(msg['content']) > 60 else ''}[/]")
                self._print()
                continue
            elif cmd == "/model":
                self._print(f"  [{label}]模型:[/] [{text}]{model_name}[/]")
                self._print(f"  [{label}]上下文:[/] [{text}]{ctx_window:,} tokens[/]")
                self._print(f"  [{label}]对话轮数:[/] [{text}]{self.session.turn_count}[/]")
                self._print(f"  [{label}]消息数:[/] [{text}]{len(self.session.messages)}[/]")
                self._print()
                continue

            # 追加用户消息
            self.session.messages.append({"role": "user", "content": user_input})

            # 调用模型
            self.session.turn_count += 1
            full_response = []
            thinking_text = ""
            is_streaming = False
            has_thinking = False

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

                    # 收集思考过程（流式）
                    if resp.thinking and resp.finish_reason == "thinking":
                        thinking_text += resp.thinking
                        has_thinking = True

                    # 流式回复内容
                    if resp.content and resp.finish_reason == "streaming":
                        is_streaming = True
                        print(resp.content, end="", flush=True)
                        full_response.append(resp.content)

                    # 非流式一次性响应（CLI 适配器等）
                    if resp.finish_reason == "stop":
                        if resp.thinking:
                            thinking_text = resp.thinking
                            has_thinking = True
                        if resp.content:
                            full_response.append(resp.content)

                # 响应渲染
                assistant_content = "".join(full_response)
                if assistant_content:
                    self.session.messages.append({"role": "assistant", "content": assistant_content})

                    if is_streaming:
                        # 流式：先换行结束，再用面板重新包裹
                        print()  # 结束流式打印
                        # 流式内容已打印到终端，不需要面板再打印一次
                    elif self.console:
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

                # 思考过程显示（放在响应后，缩短展示）
                if has_thinking and thinking_text and self.console:
                    dim_c = self.skin.color("banner_dim") if self.skin else "#B8860B"
                    # 只显示第一行或前 100 字符
                    first_line = thinking_text.split("\n")[0][:100]
                    self._print(f"[dim {dim_c}]💭 {first_line}{'...' if len(thinking_text) > 100 else ''}[/]")

            except Exception as e:
                error_color = self.skin.color("ui_error", "#ef5350") if self.skin else "#ef5350"
                self._print(f"[bold {error_color}]❌ 调用失败: {e}[/]")

            self._print()  # 空行分隔

        return self.session.turn_count
