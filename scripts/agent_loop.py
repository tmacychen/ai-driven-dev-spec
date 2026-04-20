#!/usr/bin/env python3
"""
ADDS Agent Loop — Rich 美化版

核心能力：创建 agent → 注入系统提示词 → 调用大模型 → 交互对话
集成 P0-2 上下文压缩：Token 预算管理 + 两层压缩引擎 + Session 管理
集成 P1 韧性增强：7 种终止条件 + 5 种继续条件 + PTL 恢复 + max_output_tokens 重试
使用 Rich 库实现彩色终端输出、思考过程面板、响应面板等。
"""

import asyncio
import logging
import time
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
from loop_state import (
    LoopStateMachine, LoopState, ResilienceConfig,
    TerminationReason, ContinueReason, ErrorCategory,
    TERMINATION_DESCRIPTIONS, CONTINUE_DESCRIPTIONS,
)

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

        # P0-3: 记忆管理器
        self.memory_mgr = MemoryManager(
            sessions_dir=sessions_dir,
            project_root=project_root,
        )

        # P0-4: 权限管理器
        self.permission = PermissionManager(
            project_root=project_root, mode=permission_mode
        )

        # P1: 韧性状态机
        self.resilience = LoopStateMachine(config=ResilienceConfig())
        self._loop_state: Optional[LoopState] = None

        # P1: 技能管理器
        from skill_manager import SkillManager
        self.skill_mgr = SkillManager(project_root=project_root)

        # 注入 Level 0 技能索引到 system prompt
        skill_section = self.skill_mgr.build_level0_section()
        if skill_section:
            self.session.system_prompt += "\n\n" + skill_section

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
                 "/clear", "/history", "/model", "/perm", "/skill", "/schedule"],
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
                        ("/skill [name]", "查看技能详情（Level 1）"),
                        ("/schedule", "查看定时任务列表和统计"),
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
                    self._print(f"  /skill      查看技能列表/详情")
                    self._print(f"  /schedule   查看定时任务列表/统计")
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
            elif cmd == "/skill":
                # P1: 技能渐进式披露
                from skill_manager import SkillManager
                skill_mgr = SkillManager(project_root=self.project_root)
                parts = user_input.split()
                if len(parts) >= 2:
                    skill_name = parts[1]
                    detail = skill_mgr.skill_view(skill_name)
                    if detail:
                        self._print(f"\n  [{label}]技能:[/] [{text}]{detail.name}[/]")
                        self._print(f"  [{label}]触发:[/] [{text}]{detail.trigger}[/]")
                        self._print(f"  [{label}]命令:[/] [{text}]{detail.command}[/]")
                        if detail.input_desc:
                            self._print(f"  [{label}]输入:[/] [{text}]{detail.input_desc}[/]")
                        if detail.output_desc:
                            self._print(f"  [{label}]输出:[/] [{text}]{detail.output_desc}[/]")
                        if detail.examples:
                            self._print(f"  [{label}]示例:[/]")
                            for ex in detail.examples:
                                self._print(f"    [{text}]{ex}[/]")
                        files = skill_mgr.skill_files(skill_name)
                        if files:
                            self._print(f"  [{label}]参考文件:[/]")
                            for f in files:
                                self._print(f"    [{text}]{f.path} — {f.description}[/]")
                    else:
                        self._print(f"  ❌ 未找到技能: {skill_name}")
                else:
                    # 列出所有技能
                    metas = skill_mgr.skills_list()
                    if metas:
                        self._print(f"\n  [{label}]可用技能（{len(metas)} 个）:[/]")
                        for meta in metas:
                            self._print(f"    [{text}]{meta.name}[/]: {meta.description}")
                    else:
                        self._print(f"  📭 暂无技能。使用 adds skill register 添加。")
                self._print()
                continue
            elif cmd == "/schedule":
                # P2-1: 定时调度
                from scheduler import TaskScheduler
                sched = TaskScheduler(project_root=self.project_root)
                parts = user_input.split()
                if len(parts) >= 2 and parts[1] == "stats":
                    stats = sched.get_stats()
                    self._print(f"  [{label}]总任务:[/] [{text}]{stats['total_tasks']}[/]")
                    self._print(f"  [{label}]活跃:[/] [{text}]{stats['active_tasks']}[/]")
                    self._print(f"  [{label}]暂停:[/] [{text}]{stats['paused_tasks']}[/]")
                    self._print(f"  [{label}]总执行:[/] [{text}]{stats['total_executions']}[/]")
                    daemon_status = "运行中" if stats['daemon_running'] else "未启动"
                    self._print(f"  [{label}]守护进程:[/] [{text}]{daemon_status}[/]")
                else:
                    # 列出任务
                    tasks = sched.list_tasks()
                    if tasks:
                        self._print(f"\n  [{label}]定时任务（{len(tasks)} 个）:[/]")
                        for t in tasks:
                            icon = "🟢" if t.status == "active" else "⏸️"
                            self._print(f"    {icon} [{text}]{t.task_id}[/] {t.name} — {t.cron_expr}")
                        self._print(f"\n  [{dim}]子命令: /schedule stats[/]")
                    else:
                        self._print(f"  📭 暂无定时任务。使用 adds schedule add 添加。")
                self._print()
                continue

            # 追加用户消息
            self.session.messages.append({"role": "user", "content": user_input})

            # P1: 韧性增强 — 支持重试/续写/PTL恢复的模型调用
            self.session.turn_count += 1
            self.resilience.reset_session_stats()
            final_assistant_content = await self._call_model_with_resilience()

            if final_assistant_content:
                self.session.messages.append(
                    {"role": "assistant", "content": final_assistant_content}
                )

            self._print()  # 空行分隔

            # P0-2: 检查 token 预算并发出警告
            warning = self.compactor.get_warning()
            if warning:
                warn_color = self.skin.color("ui_error", "#ef5350") if self.skin else "#ef5350"
                self._print(f"[bold {warn_color}]{warning}[/]\n")

            # P1: 检查是否需要 Layer2 压缩（PTL 恢复后）
            if self.budget.is_hard_limit():
                warn_color = self.skin.color("ui_error", "#ef5350") if self.skin else "#ef5350"
                self._print(f"[bold {warn_color}]⚠️  Token 硬限制已达到，正在压缩上下文...[/]")
                self._try_compact_for_ptl()

        # P0-2: Session 结束 → 归档
        self._archive_session()

        return self.session.turn_count

    async def _call_model_with_resilience(self) -> str:
        """P1: 韧性增强的模型调用

        支持：
        - max_output_tokens 续写恢复
        - PTL (prompt-too-long) 压缩恢复
        - 环境错误重试 + 指数退避
        - 用户中止检测

        Returns:
            最终的助手回复内容
        """
        max_retries = self.resilience.config.max_output_tokens_retries
        full_response_parts: List[str] = []
        is_continuation = False  # 是否是续写（max_output_tokens 恢复）

        while True:
            full_response = []
            thinking_text = ""
            is_streaming = False
            has_thinking = False
            finish_reason = "stop"
            error_occurred = None

            try:
                # 构建消息：如果是续写，添加续写提示
                messages = self.session.messages
                if is_continuation and full_response_parts:
                    # 续写模式：在上一次回复后追加续写提示
                    messages = list(self.session.messages)
                    # 移除最后一条不完整的 assistant 消息（如果有）
                    # 续写提示：让模型从断点继续
                    continuation_prompt = (
                        "（接上文，请继续完成被截断的回复）"
                    )
                    messages = messages + [
                        {"role": "user", "content": continuation_prompt}
                    ]

                async for resp in self.model.chat(
                    messages,
                    system_prompt=self.session.system_prompt or None,
                    stream=True,
                ):
                    if resp.finish_reason == "error":
                        error_color = self.skin.color("ui_error", "#ef5350") if self.skin else "#ef5350"
                        self._print(f"[bold {error_color}]❌ {resp.content}[/]")
                        finish_reason = "error"
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

                    # P1: 检测 length 截断
                    if resp.finish_reason == "length":
                        finish_reason = "length"
                        if resp.content:
                            full_response.append(resp.content)

            except KeyboardInterrupt:
                # 用户中止 → 记录终止
                self._loop_state = self.resilience.evaluate_response(
                    finish_reason="stop", is_user_abort=True
                )
                warn_color = self.skin.color("ui_error", "#ef5350") if self.skin else "#ef5350"
                self._print(f"\n[{warn_color}]⚠️  流式输出已中止[/]")
                break

            except Exception as e:
                error_occurred = e
                error_color = self.skin.color("ui_error", "#ef5350") if self.skin else "#ef5350"
                self._print(f"[bold {error_color}]❌ 调用失败: {e}[/]")

            # P1: 评估终止/继续条件
            is_hard_limit = self.budget.is_hard_limit()
            self._loop_state = self.resilience.evaluate_response(
                finish_reason=finish_reason,
                error=error_occurred,
                is_hard_limit=is_hard_limit,
            )

            # 处理终止
            if self._loop_state.should_terminate:
                desc = TERMINATION_DESCRIPTIONS.get(
                    self._loop_state.termination_reason, "未知原因"
                )
                dim_c = self.skin.color("banner_dim") if self.skin else "#B8860B"
                self._print(f"[dim {dim_c}]{desc}[/]")
                # 如果有部分响应，仍然返回
                if full_response:
                    full_response_parts.append("".join(full_response))
                break

            # 处理继续
            if self._loop_state.should_continue:
                reason = self._loop_state.continue_reason
                desc = CONTINUE_DESCRIPTIONS.get(reason, "继续...")
                accent = self.skin.color("ui_accent") if self.skin else "#FFBF00"
                self._print(f"\n[bold {accent}]🔄 {desc}[/]")

                if reason == ContinueReason.MAX_OUTPUT_TOKENS:
                    # max_output_tokens 恢复：保存当前内容，续写
                    if full_response:
                        full_response_parts.append("".join(full_response))
                    is_continuation = True
                    # 冷却等待
                    time.sleep(self.resilience.config.max_output_tokens_cooldown)
                    continue

                elif reason == ContinueReason.PROMPT_TOO_LONG:
                    # PTL 恢复：压缩上下文后重试
                    if self._try_compact_for_ptl():
                        # 压缩成功 → 重试
                        time.sleep(self.resilience.get_backoff_time(
                            self._loop_state.ptl_retry_count
                        ))
                        continue
                    else:
                        # 压缩失败 → 终止
                        dim_c = self.skin.color("banner_dim") if self.skin else "#B8860B"
                        self._print(
                            f"[dim {dim_c}]⛔ 压缩失败，无法恢复[/]"
                        )
                        break

                elif reason == ContinueReason.ERROR_RETRY:
                    # 错误重试：退避等待
                    if full_response:
                        full_response_parts.append("".join(full_response))
                    backoff = self.resilience.get_backoff_time(
                        self._loop_state.error_retry_count
                    )
                    dim_c = self.skin.color("banner_dim") if self.skin else "#B8860B"
                    self._print(
                        f"[dim {dim_c}]⏳ 等待 {backoff:.1f}s 后重试...[/]"
                    )
                    time.sleep(backoff)
                    continue

                elif reason == ContinueReason.HOOK_RETRY:
                    continue

            # 正常完成（无终止也无继续）
            if full_response:
                full_response_parts.append("".join(full_response))

            # 渲染非流式响应
            assistant_content = "".join(full_response)
            if assistant_content and not is_streaming and self.console:
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

            # 流式输出换行结束
            if is_streaming:
                print()

            # 思考过程显示
            if has_thinking and thinking_text and self.console:
                dim_c = self.skin.color("banner_dim") if self.skin else "#B8860B"
                first_line = thinking_text.split("\n")[0][:100]
                self._print(f"[dim {dim_c}]💭 {first_line}{'...' if len(thinking_text) > 100 else ''}[/]")

            break

        # 合并所有部分（包括续写内容）
        return "".join(full_response_parts)

    def _try_compact_for_ptl(self) -> bool:
        """P1: PTL 恢复 — 压缩上下文以降低 Token 使用量

        策略：
        1. 先尝试 Layer1 压缩（工具输出替换为摘要）
        2. 如果仍然超限，执行 Layer2 归档
        3. 归档后开始新 session

        Returns:
            True 如果压缩成功，False 如果失败
        """
        try:
            target = self.resilience.config.ptl_compression_target

            # Layer1: 压缩工具输出
            if self.budget.utilization > target:
                compressed_msgs, results = self.compactor.layer1_compress_batch(
                    self.session.messages
                )
                if results:
                    self.session.messages = compressed_msgs

            # Layer2: 如果仍然超限，归档
            if self.budget.utilization > target:
                result = self.compactor.layer2_archive(model_interface=self.model)
                if result:
                    # 清空当前对话历史，保留系统提示词
                    self.session.messages.clear()
                    self.session.turn_count = 0
                    # 重置预算
                    self.budget._history = 0
                    self.budget._tool_results = 0
                    logger.info(f"PTL recovery: Layer2 archive completed, new session")
                    return True

            return self.budget.utilization <= target

        except Exception as e:
            logger.error(f"PTL compaction failed: {e}")
            return False

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
                        # P0: 基于规则评估（同步），P1 将接入 LLM
                        evaluations = self.memory_mgr._rule_based_evaluate(
                            mem_content, role=self.agent_role
                        )
                        # 执行升级（同步写入固定记忆）
                        for ev in evaluations:
                            if ev.should_upgrade and ev.confidence >= 0.6:
                                try:
                                    # 同步版升级：直接写入 index.mem
                                    upgraded = self.memory_mgr._upgrade_memory_sync(ev)
                                    if upgraded:
                                        logger.info(
                                            f"Memory upgraded: [{ev.category}] {ev.content[:40]} "
                                            f"(confidence={ev.confidence:.2f})"
                                        )
                                except Exception as ue:
                                    logger.debug(f"Upgrade skipped: {ue}")

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
