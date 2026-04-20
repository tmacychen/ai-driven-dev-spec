#!/usr/bin/env python3
"""
ADDS Agent Loop — CLI 界面层（基于 AgentCore 共享核心层）

核心逻辑全部由 AgentCore 提供，此文件只做 CLI 界面适配：
- Rich 彩色终端输出
- prompt_toolkit 交互输入
- 命令处理（/help, /quit, /model 等）
"""

import asyncio
import logging
import re
import sys
from typing import Optional

from agent_core import AgentCore, AgentCallbacks, BUILTIN_ROLES
from permission_manager import PermissionDecision

logger = logging.getLogger(__name__)

# prompt_toolkit 用于处理中文输入的退格问题
try:
    from prompt_toolkit import PromptSession
    from prompt_toolkit.formatted_text import HTML
    HAS_PT = True
except ImportError:
    HAS_PT = False


class CLICallbacks:
    """CLI 的 AgentCallbacks 实现 — Rich 彩色终端输出"""

    def __init__(self, console=None, skin=None):
        self.console = console
        self.skin = skin
        self._thinking_shown = False
        self._streaming_started = False

    def _color(self, key: str, fallback: str = "#FFF8DC") -> str:
        return self.skin.color(key, fallback) if self.skin else fallback

    def _print(self, *args, **kwargs):
        if self.console:
            self.console.print(*args, **kwargs)
        else:
            msg = " ".join(str(a) for a in args)
            msg = re.sub(r'\[/?[^\]]*\]', '', msg)
            print(msg, **kwargs)

    def on_chunk(self, text: str):
        """流式文本片段 → 直接打印"""
        if not self._streaming_started:
            self._streaming_started = True
            # 清除 thinking 行
            if self._thinking_shown:
                print("\r" + " " * 40 + "\r", end="", flush=True)
        print(text, end="", flush=True)

    def on_thinking(self, text: str, is_first: bool):
        """思考过程 → 紧凑指示器"""
        if is_first and not self._thinking_shown:
            self._thinking_shown = True
            dim = self._color("banner_dim", "#B8860B")
            sys.stdout.write(f"\r[dim {dim}]🧠 思考中... [/]")
            sys.stdout.flush()

    def on_tool_call(self, tool_name: str, args: dict):
        """工具调用状态"""
        accent = self._color("ui_accent", "#FFBF00")
        dim = self._color("banner_dim", "#B8860B")
        self._print(f"[{dim}]🔧 调用工具: [{accent}]{tool_name}[/]")

    def on_status(self, status: str):
        """Agent Loop 状态变化"""
        # CLI 用 thinking/streaming 指示器，不额外渲染

    def on_done(self, full_text: str):
        """完整回复完成"""
        if self._streaming_started:
            print()  # 流式输出换行
            self._streaming_started = False

        if full_text and not self._streaming_started and self.console:
            # 非流式响应 → Rich Panel
            border = self._color("response_border", "#FFD700")
            label = (self.skin.branding("response_label", " ⚡ ADDS ")
                     if self.skin else " ⚡ ADDS ")
            from rich.panel import Panel
            self.console.print(Panel(
                full_text,
                title=f"[{border}]{label}[/]",
                border_style=border,
                padding=(0, 1),
            ))

        # 清除 thinking 指示器
        if self._thinking_shown and not full_text:
            print("\r" + " " * 40 + "\r", end="", flush=True)

        self._thinking_shown = False

    def on_error(self, error_text: str):
        """错误消息"""
        err_c = self._color("ui_error", "#ef5350")
        self._print(f"[bold {err_c}]{error_text}[/]")

    def on_warning(self, warning_text: str):
        """警告消息"""
        warn_c = self._color("ui_error", "#ef5350")
        self._print(f"[bold {warn_c}]{warning_text}[/]")

    def on_permission_ask(self, decision: PermissionDecision) -> bool:
        """权限确认 → CLI 终端交互"""
        accent = self._color("ui_accent", "#FFBF00")
        label = self._color("ui_label", "#4dd0e1")
        text = self._color("banner_text", "#FFF8DC")

        self._print(f"\n[{accent}]🔐 权限确认[/]")
        self._print(f"  [{label}]工具:[/] [{text}]{decision.tool}[/]")
        if decision.command:
            self._print(f"  [{label}]命令:[/] [{text}]{decision.command[:100]}[/]")
        self._print(f"  [{label}]原因:[/] [{text}]{decision.reason}[/]")

        try:
            answer = input(f"  允许？[y/N] ").strip().lower()
            return answer in ("y", "yes", "是")
        except (EOFError, KeyboardInterrupt):
            return False

    def on_compact(self, strategy: str, saved_tokens: int):
        """压缩通知"""
        dim = self._color("banner_dim", "#B8860B")
        self._print(f"[dim {dim}]📦 压缩 ({strategy}): 节省 {saved_tokens:,} tokens[/]")

    def on_continuation(self, attempt: int):
        """续写通知"""
        accent = self._color("ui_accent", "#FFBF00")
        self._print(f"[bold {accent}]🔄 续写恢复 (第 {attempt} 次)[/]")

    def reset(self):
        """重置流式状态（每轮对话开始前调用）"""
        self._thinking_shown = False
        self._streaming_started = False


class AgentLoop:
    """
    Agent Loop — CLI 界面层

    核心逻辑由 AgentCore 提供，此类只做：
    1. 命令行交互（prompt_toolkit / input）
    2. 命令处理（/help, /quit, /model, /perm, /skill, /schedule）
    3. Rich 美化输出
    """

    def __init__(self, model, system_prompt: str = "",
                 console=None, skin=None, project_root: str = ".",
                 agent_role: str = "", feature: str = "",
                 permission_mode: str = "default"):
        self.console = console
        self.skin = skin

        # ── 创建 AgentCore ────────────────────────────
        self.core = AgentCore(
            model=model,
            project_root=project_root,
            agent_role=agent_role or "pm",
            feature=feature,
            permission_mode=permission_mode,
        )

        # 如果传入了自定义 system_prompt，覆盖默认
        if system_prompt:
            self.core.system_prompt = system_prompt

        # ── CLI 回调 ──────────────────────────────────
        self._cli_cb = CLICallbacks(console=console, skin=skin)

        # ── 如果没有 console/skin，使用简单模式 ───────
        if self.console is None:
            try:
                from skins import create_console, SkinConfig
                self.console = create_console()
                self.skin = SkinConfig({})
                self._cli_cb.console = self.console
                self._cli_cb.skin = self.skin
            except ImportError:
                self.console = None
                self.skin = None

        # ── prompt_toolkit session ────────────────────
        self._pt_session = None
        if HAS_PT:
            from prompt_toolkit.key_binding import KeyBindings
            from prompt_toolkit.completion import WordCompleter

            kb = KeyBindings()

            @kb.add('escape', 'enter')
            @kb.add('c-j')
            def _(event):
                event.current_buffer.insert_text('\n')

            command_completer = WordCompleter(
                ["/help", "/h", "/?", "/keys", "/quit", "/exit", "/q",
                 "/clear", "/history", "/model", "/perm", "/skill", "/schedule"],
                ignore_case=True,
            )

            self._pt_session = PromptSession(
                multiline=False,
                key_bindings=kb,
                completer=command_completer,
                enable_open_in_editor=True,
            )

    def _print(self, *args, **kwargs):
        if self.console:
            self.console.print(*args, **kwargs)
        else:
            msg = " ".join(str(a) for a in args)
            msg = re.sub(r'\[/?[^\]]*\]', '', msg)
            print(msg, **kwargs)

    async def run(self):
        """主循环：交互式对话"""
        model_name = self.core.model.get_model_name()
        ctx_window = self.core.model.get_context_window()

        accent = self._color("ui_accent", "#FFBF00")
        text = self._color("banner_text", "#FFF8DC")
        dim = self._color("banner_dim", "#B8860B")
        label = self._color("ui_label", "#4dd0e1")
        prompt_color = self._color("prompt", "#FFF8DC")
        prompt_symbol = self.skin.prompt_symbol if self.skin else "❯"

        self._print(f"[bold {accent}]🤖 Agent 已启动[/]")
        self._print(f"  [{label}]模型:[/] [{text}]{model_name}[/]")
        self._print(f"  [{label}]上下文:[/] [{text}]{ctx_window:,} tokens[/]")
        if self.core.system_prompt:
            sp = self.core.system_prompt[:80]
            self._print(f"  [{label}]角色设定:[/] [{text}]{sp}[/]")
        self._print(f"\n[dim {dim}]💡 输入消息开始对话 · /help 帮助 · /keys 快捷键 · /quit 退出[/]\n")

        # 初始化 session
        self.core.init_session()

        while True:
            try:
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

            # ── 命令处理 ──────────────────────────────
            cmd = user_input.lower().split()[0]
            if cmd in ("/quit", "/exit", "/q"):
                goodbye = self.skin.branding("goodbye", "Goodbye!") if self.skin else "再见！"
                self._print(f"[bold]{goodbye}[/]")
                break
            elif cmd in ("/help", "/h", "/?"):
                self._cmd_help(accent, dim, label, text)
                continue
            elif cmd == "/keys":
                self._cmd_keys(accent, dim)
                continue
            elif cmd == "/clear":
                self.core.clear_messages()
                ok_color = self._color("ui_ok", "#4caf50")
                self._print(f"[{ok_color}]✅ 对话历史已清空[/]\n")
                continue
            elif cmd == "/history":
                self._cmd_history(dim, accent, text, prompt_color)
                continue
            elif cmd == "/model":
                self._cmd_model(label, text)
                continue
            elif cmd == "/perm":
                self._cmd_perm(user_input, label, text, dim)
                continue
            elif cmd == "/skill":
                self._cmd_skill(user_input, label, text)
                continue
            elif cmd == "/schedule":
                self._cmd_schedule(user_input, label, text, dim)
                continue

            # ── 发送消息 ──────────────────────────────
            self._cli_cb.reset()
            await self.core.send_message(user_input, callbacks=self._cli_cb)
            self._print()  # 空行分隔

        # 归档 session
        self.core.archive_session()
        return self.core.turn_count

    # ── 命令处理方法 ────────────────────────────────────

    def _color(self, key: str, fallback: str = "#FFF8DC") -> str:
        return self.skin.color(key, fallback) if self.skin else fallback

    def _cmd_help(self, accent, dim, label, text):
        header = self.skin.branding("help_header", "Available Commands") if self.skin else "Available Commands"
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
            self.console.print(Panel(t, title=f"[bold {accent}]{header}[/]", border_style=dim, padding=(0, 1)))
        else:
            self._print(f"\n[bold {accent}]{header}[/]")
            self._print("  /help       显示此帮助信息")
            self._print("  /keys       显示快捷键列表")
            self._print("  /quit       退出对话")
            self._print("  /clear      清空对话历史")
            self._print("  /history    查看对话历史")
            self._print("  /model      显示模型信息")
            self._print("  /perm       显示权限状态")
            self._print("  /skill      查看技能列表/详情")
            self._print("  /schedule   查看定时任务列表/统计")
        self._print()

    def _cmd_keys(self, accent, dim):
        if self.console:
            from rich.table import Table
            from rich.panel import Panel
            from rich.box import ROUNDED
            t = Table(show_header=False, box=ROUNDED, border_style=dim, padding=(0, 1))
            t.add_column("Key", style=f"bold {accent}", width=24)
            t.add_column("Action", style=text)
            t.add_column("Note", style=f"dim {dim}")
            text = self._color("banner_text", "#FFF8DC")
            for key, action, note in [
                ("Enter", "提交消息", "发送当前输入"),
                ("Esc + Enter", "插入换行", "多行输入，不提交"),
                ("Ctrl+J", "插入换行", "等同 Esc+Enter"),
                ("Ctrl+X Ctrl+E", "打开编辑器", "用 $EDITOR 编辑多行内容"),
                ("↑ / ↓", "浏览历史", "上/下翻阅历史输入"),
                ("Ctrl+C", "退出", "强制退出对话"),
                ("Tab", "补全命令", "补全 / 开头的命令"),
            ]:
                t.add_row(key, action, note)
            self.console.print(Panel(t, title=f"[bold {accent}]⌨  Keybindings[/]", border_style=dim, padding=(0, 1)))
        else:
            self._print(f"\n[bold {accent}]⌨  Keybindings[/]")
            self._print("  Enter            提交消息")
            self._print("  Esc+Enter        插入换行")
            self._print("  Ctrl+J           插入换行")
            self._print("  Ctrl+X Ctrl+E    打开编辑器")
            self._print("  ↑/↓              浏览历史")
            self._print("  Ctrl+C           退出")
        self._print()

    def _cmd_history(self, dim, accent, text, prompt_color):
        if not self.core.messages:
            self._print(f"[dim {dim}]（暂无对话历史）[/]")
        else:
            self._print(f"[bold {accent}]📜 对话历史 ({len(self.core.messages)} 条)[/]")
            for msg in self.core.messages[-6:]:
                role = msg["role"]
                content = msg["content"][:60].replace("\n", " ")
                role_color = prompt_color if role == "user" else dim
                self._print(f"  [{role_color}]{role}:[/] [{text}]{content}{'...' if len(msg['content']) > 60 else ''}[/]")
        self._print()

    def _cmd_model(self, label, text):
        model_name = self.core.model.get_model_name()
        ctx_window = self.core.model.get_context_window()
        self._print(f"  [{label}]模型:[/] [{text}]{model_name}[/]")
        self._print(f"  [{label}]上下文:[/] [{text}]{ctx_window:,} tokens[/]")
        self._print(f"  [{label}]对话轮数:[/] [{text}]{self.core.turn_count}[/]")
        self._print(f"  [{label}]消息数:[/] [{text}]{len(self.core.messages)}[/]")
        self._print(f"  [{label}]Token 使用:[/] [{text}]{self.core.budget.used:,}/{self.core.budget.context_window:,} ({self.core.budget.utilization:.1%})[/]")
        self._print(f"  [{label}]推荐操作:[/] [{text}]{self.core.budget.recommend_action()}[/]")
        self._print()

    def _cmd_perm(self, user_input, label, text, dim):
        stats = self.core.permission.get_stats()
        self._print(f"  [{label}]权限模式:[/] [{text}]{stats['mode']}[/]")
        self._print(f"  [{label}]检查次数:[/] [{text}]{stats['total_checks']}[/]")
        self._print(f"  [{label}]允许/确认/拒绝:[/] [{text}]{stats['allowed']}/{stats['asked']}/{stats['denied']}[/]")
        if stats['cooldown_tools']:
            self._print(f"  [{label}]冷却中:[/] [{text}]{', '.join(stats['cooldown_tools'])}[/]")
        self._print(f"\n  [{dim}]权限模式: default(推荐) / plan(只读) / auto(AI决策) / bypass(危险)[/]")
        self._print(f"  [{dim}]切换模式: /perm mode <mode>[/]")
        parts = user_input.split()
        if len(parts) >= 3 and parts[1] == "mode":
            new_mode = parts[2]
            if new_mode in ("default", "plan", "auto", "bypass"):
                self.core.permission.set_mode(new_mode)
                warn_c = self._color("ui_error", "#ef5350")
                if new_mode == "bypass":
                    self._print(f"\n[bold {warn_c}]⚠️  bypass 模式已启用！所有操作将自动放行，请谨慎使用！[/]")
                ok_c = self._color("ui_ok", "#4caf50")
                self._print(f"[{ok_c}]✅ 权限模式已切换为: {new_mode}[/]")
            else:
                self._print(f"  ❌ 未知模式: {new_mode}")
        self._print()

    def _cmd_skill(self, user_input, label, text):
        from skill_manager import SkillManager
        skill_mgr = SkillManager(project_root=str(self.core.project_root))
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
            metas = skill_mgr.skills_list()
            if metas:
                self._print(f"\n  [{label}]可用技能（{len(metas)} 个）:[/]")
                for meta in metas:
                    self._print(f"    [{text}]{meta.name}[/]: {meta.description}")
            else:
                self._print("  📭 暂无技能。使用 adds skill register 添加。")
        self._print()

    def _cmd_schedule(self, user_input, label, text, dim):
        from scheduler import TaskScheduler
        sched = TaskScheduler(project_root=str(self.core.project_root))
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
            tasks = sched.list_tasks()
            if tasks:
                self._print(f"\n  [{label}]定时任务（{len(tasks)} 个）:[/]")
                for t in tasks:
                    icon = "🟢" if t.status == "active" else "⏸️"
                    self._print(f"    {icon} [{text}]{t.task_id}[/] {t.name} — {t.cron_expr}")
                self._print(f"\n  [{dim}]子命令: /schedule stats[/]")
            else:
                self._print("  📭 暂无定时任务。使用 adds schedule add 添加。")
        self._print()
