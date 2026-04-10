#!/usr/bin/env python3
"""
ADDS Agent Loop — Rich 美化版

核心能力：创建 agent → 注入系统提示词 → 调用大模型 → 交互对话
集成 P0-2 上下文压缩：Token 预算管理 + 两层压缩引擎 + Session 管理
使用 Rich 库实现彩色终端输出、思考过程面板、响应面板等。
"""

import asyncio
import logging
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Optional, List, Dict, Any

from model.base import ModelInterface
from token_budget import TokenBudget, estimate_tokens, load_budget_config
from session_manager import SessionManager
from context_compactor import ContextCompactor
from summary_decision_engine import SummaryStrategy
from memory_manager import MemoryManager
from permission_manager import PermissionManager, confirm_action_with_session

logger = logging.getLogger(__name__)

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
    4. P0-2: Token 预算管理 + 两层压缩 + Session 归档
    """

    def __init__(self, model: ModelInterface, system_prompt: str = "",
                 console=None, skin=None, project_root: str = ".",
                 agent_role: str = "", feature: str = "",
                 permission_mode: str = "default"):
        self.model = model
        self.session = AgentSession(system_prompt=system_prompt)
        self.console = console
        self.skin = skin
        self.project_root = project_root
        self.agent_role = agent_role
        self.feature = feature

        # P0-2: Token 预算 + Session 管理 + 压缩引擎
        ctx_window = model.get_context_window()
        budget_config = load_budget_config(project_root)
        sessions_dir = f"{project_root}/.ai/sessions"

        self.budget = TokenBudget(context_window=ctx_window, config=budget_config)
        self.session_mgr = SessionManager(sessions_dir=sessions_dir)
        self.compactor = ContextCompactor(self.budget, self.session_mgr)

        # P0-4: 权限管理器
        self.permission = PermissionManager(
            project_root=project_root, mode=permission_mode
        )

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
            from prompt_toolkit.completion import WordCompleter

            kb = KeyBindings()

            @kb.add('escape', 'enter')
            @kb.add('c-j')  # Ctrl+J (Shift+Enter on some terminals)
            def _(event):
                """插入换行而非提交"""
                event.current_buffer.insert_text('\n')

            # 命令补全
            command_completer = WordCompleter(
                ["/help", "/h", "/?", "/keys", "/quit", "/exit", "/q",
                 "/clear", "/history", "/model", "/perm"],
                ignore_case=True,
            )

            self._pt_session = PromptSession(
                multiline=False,
                key_bindings=kb,
                completer=command_completer,
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
        self._print(f"\n[dim {dim}]💡 输入消息开始对话 · /help 帮助 · /keys 快捷键 · /quit 退出[/]\n")

        # P0-2: 初始化 session 和 token 预算
        self._init_session_budget(ctx_window)

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
            elif cmd in ("/help", "/h", "/?"):
                help_header = self.skin.branding("help_header", "Available Commands") if self.skin else "Available Commands"
                if self.console:
                    from rich.table import Table
                    from rich.panel import Panel
                    from rich.box import ROUNDED
                    t = Table(show_header=False, box=ROUNDED, border_style=dim, padding=(0, 1))
                    t.add_column("Command", style=f"bold {label}", width=26)
                    t.add_column("Description", style=text)
                    for name, desc in [
                        ("/help, /h, /?", "显示此帮助信息"),
                        ("/keys", "显示快捷键列表"),
                        ("/quit, /exit, /q", "退出对话"),
                        ("/clear", "清空对话历史"),
                        ("/history", "查看对话历史摘要"),
                        ("/model", "显示当前模型信息"),
                        ("/perm", "显示权限状态和统计"),
                    ]:
                        t.add_row(name, desc)
                    self.console.print(Panel(t, title=f"[bold {accent}]{help_header}[/]", border_style=dim, padding=(0, 1)))
                else:
                    self._print(f"\n[bold {accent}]{help_header}[/]")
                    self._print(f"  /help       显示此帮助信息")
                    self._print(f"  /keys       显示快捷键列表")
                    self._print(f"  /quit       退出对话")
                    self._print(f"  /clear      清空对话历史")
                    self._print(f"  /history    查看对话历史")
                    self._print(f"  /model      显示模型信息")
                    self._print(f"  /perm       显示权限状态")
                self._print()
                continue
            elif cmd == "/keys":
                if self.console:
                    from rich.table import Table
                    from rich.panel import Panel
                    from rich.box import ROUNDED
                    t = Table(show_header=False, box=ROUNDED, border_style=dim, padding=(0, 1))
                    t.add_column("Key", style=f"bold {accent}", width=24)
                    t.add_column("Action", style=text)
                    t.add_column("Note", style=f"dim {dim}")
                    keys = [
                        ("Enter", "提交消息", "发送当前输入"),
                        ("Esc + Enter", "插入换行", "多行输入，不提交"),
                        ("Ctrl+J", "插入换行", "等同 Esc+Enter"),
                        ("Ctrl+X Ctrl+E", "打开编辑器", "用 $EDITOR 编辑多行内容"),
                        ("↑ / ↓", "浏览历史", "上/下翻阅历史输入"),
                        ("Ctrl+C", "退出", "强制退出对话"),
                        ("Tab", "补全命令", "补全 / 开头的命令"),
                    ]
                    for key, action, note in keys:
                        t.add_row(key, action, note)
                    self.console.print(Panel(t, title=f"[bold {accent}]⌨  Keybindings[/]", border_style=dim, padding=(0, 1)))
                else:
                    self._print(f"\n[bold {accent}]⌨  Keybindings[/]")
                    self._print(f"  Enter            提交消息")
                    self._print(f"  Esc+Enter        插入换行")
                    self._print(f"  Ctrl+J           插入换行")
                    self._print(f"  Ctrl+X Ctrl+E    打开编辑器")
                    self._print(f"  ↑/↓              浏览历史")
                    self._print(f"  Ctrl+C           退出")
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
                # P0-2: 显示 token 预算
                self._print(f"  [{label}]Token 使用:[/] [{text}]{self.budget.used:,}/{self.budget.context_window:,} ({self.budget.utilization:.1%})[/]")
                self._print(f"  [{label}]推荐操作:[/] [{text}]{self.budget.recommend_action()}[/]")
                self._print()
                continue
            elif cmd == "/perm":
                # P0-4: 权限状态
                stats = self.permission.get_stats()
                self._print(f"  [{label}]权限模式:[/] [{text}]{stats['mode']}[/]")
                self._print(f"  [{label}]检查次数:[/] [{text}]{stats['total_checks']}[/]")
                self._print(f"  [{label}]允许/确认/拒绝:[/] [{text}]{stats['allowed']}/{stats['asked']}/{stats['denied']}[/]")
                if stats['cooldown_tools']:
                    self._print(f"  [{label}]冷却中:[/] [{text}]{', '.join(stats['cooldown_tools'])}[/]")
                self._print(f"\n  [{dim}]权限模式: default(推荐) / plan(只读) / auto(AI决策) / bypass(危险)[/]")
                self._print(f"  [{dim}]切换模式: /perm mode <mode>[/]")
                # 子命令: /perm mode <mode>
                parts = user_input.split()
                if len(parts) >= 3 and parts[1] == "mode":
                    new_mode = parts[2]
                    if new_mode in ("default", "plan", "auto", "bypass"):
                        self.permission.set_mode(new_mode)
                        warn_c = self.skin.color("ui_error", "#ef5350") if self.skin else "#ef5350"
                        if new_mode == "bypass":
                            self._print(f"\n[bold {warn_c}]⚠️  bypass 模式已启用！所有操作将自动放行，请谨慎使用！[/]")
                        ok_c = self.skin.color("ui_ok", "#4caf50") if self.skin else "#4caf50"
                        self._print(f"[{ok_c}]✅ 权限模式已切换为: {new_mode}[/]")
                    else:
                        self._print(f"  ❌ 未知模式: {new_mode}")
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

            # P0-2: 检查 token 预算并发出警告
            warning = self.compactor.get_warning()
            if warning:
                warn_color = self.skin.color("ui_error", "#ef5350") if self.skin else "#ef5350"
                self._print(f"[bold {warn_color}]{warning}[/]\n")

        # P0-2: Session 结束 → 归档
        self._archive_session()

        return self.session.turn_count

    def _init_session_budget(self, ctx_window: int) -> None:
        """P0-2: 初始化 session 和 token 预算"""
        # 创建 session
        self._session_id = self.session_mgr.create_session(
            agent=self.agent_role,
            feature=self.feature,
        )

        # 分配系统提示词和记忆的 token 预算
        sp_tokens = estimate_tokens(self.session.system_prompt) if self.session.system_prompt else 0
        self.budget.allocate(system_prompt=sp_tokens, memory=0)

        logger.debug(
            f"Session initialized: {self._session_id}, "
            f"SP tokens: {sp_tokens}, budget: {self.budget.summary()}"
        )

    def _archive_session(self) -> None:
        """P0-2: Session 归档 + P0-3: 记忆进化"""
        if not self._session_id:
            return

        try:
            result = self.compactor.layer2_archive(model_interface=self.model)
            if result:
                logger.info(
                    f"Session archived: {result.session_id}, "
                    f"mem: {result.mem_path}"
                )

                # P0-3: 记忆进化评估
                try:
                    mem_path = Path(result.mem_path)
                    if mem_path.exists():
                        mem_content = mem_path.read_text(encoding="utf-8")
                        evaluations = asyncio.get_event_loop().run_until_complete(
                            self.memory_mgr.evaluate_and_upgrade(
                                mem_content, role=self.agent_role
                            )
                        )
                        for ev in evaluations:
                            if ev.should_upgrade:
                                logger.info(
                                    f"Memory upgraded: [{ev.category}] {ev.content[:40]} "
                                    f"(confidence={ev.confidence:.2f})"
                                )

                        # 添加记忆索引
                        self.memory_mgr.add_index_entry(
                            time=datetime.now().strftime("%m-%d %H:%M"),
                            file=f"{result.session_id}.mem",
                            summary=f"Session 归档 (agent={self.agent_role})",
                            priority="高" if self.session.turn_count > 5 else "中",
                        )
                except Exception as e:
                    logger.warning(f"Memory evolution failed: {e}")

        except Exception as e:
            logger.error(f"Session archive failed: {e}")
