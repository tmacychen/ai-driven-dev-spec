"""
ADDSApp — 主应用（Agent 工作区管理器）

基于 Textual 框架，实现多 Agent 工作区 TUI
"""

from __future__ import annotations

import asyncio
import sys
from pathlib import Path
from typing import Optional

from textual.app import App, ComposeResult
from textual.binding import Binding
from textual.css.query import NoMatches
from textual.widgets import Footer, TabbedContent, TabPane

from tui.state import AppState, WorkspaceState
from tui.skin_adapter import role_color, role_icon
from tui.widgets.header import ADDSHeader
from tui.widgets.workspace_tab import WorkspaceTab
from tui.widgets.permission_sidebar import PermissionSidebar
from tui.workspace_manager import WorkspaceManager, BUILTIN_ROLES

# 角色选择器（简单文本菜单，后续可升级为 Modal）
ROLE_CHOICES = list(BUILTIN_ROLES.keys())


class ADDSApp(App):
    """ADDS TUI 主应用"""

    CSS = """
    Screen {
        layout: horizontal;
    }
    #main-area {
        width: 1fr;
        height: 1fr;
        layout: vertical;
    }
    TabbedContent {
        height: 1fr;
    }
    TabbedContent ContentSwitcher {
        height: 1fr;
    }
    TabPane {
        height: 1fr;
        padding: 0;
    }
    """

    BINDINGS = [
        Binding("ctrl+q", "quit", "退出", show=True),
        Binding("ctrl+n", "new_agent", "新建Agent", show=True),
        Binding("ctrl+w", "close_agent", "关闭Agent", show=True),
        Binding("ctrl+tab", "next_tab", "下一个", show=False),
        Binding("f4", "toggle_perm", "权限面板", show=True),
        Binding("f1", "show_help", "帮助", show=True),
    ]

    def __init__(self, model=None, project_root: str = ".",
                 skin=None, perm_mode: str = "default", **kwargs) -> None:
        super().__init__(**kwargs)
        self._model = model
        self._project_root = project_root
        self._skin = skin
        self._perm_mode = perm_mode

        self.app_state = AppState()
        self.app_state.permission_mode = perm_mode
        self.wm = WorkspaceManager(self.app_state, project_root)
        if model:
            self.wm.set_model(model)

    def compose(self) -> ComposeResult:
        yield ADDSHeader(id="header")
        from textual.containers import Horizontal
        with Horizontal(id="main-area"):
            yield TabbedContent(id="tabs")
            yield PermissionSidebar(id="perm-sidebar")
        yield Footer()

    def on_mount(self) -> None:
        """启动时创建默认 PM Agent"""
        self._update_header()
        # 创建第一个工作区
        self._create_workspace_tab("pm")

    # ── Agent 管理 ───────────────────────────────────────────────

    def _create_workspace_tab(self, agent_role: str, task_context: str = "") -> None:
        """创建新的 Agent 工作区标签页"""
        ws = self.wm.create_workspace(agent_role, task_context)
        icon = role_icon(agent_role)
        label = f"{icon} {ws.label}"
        workspace_widget = WorkspaceTab(workspace=ws, id=f"ws-{ws.workspace_id}")
        tab_pane = TabPane(label, workspace_widget, id=f"tab-{ws.workspace_id}")
        tabs = self.query_one("#tabs", TabbedContent)
        self.run_worker(self._add_tab(tabs, tab_pane, ws.workspace_id), exclusive=False)
        self._update_header()

    async def _add_tab(self, tabs: TabbedContent, pane: TabPane, workspace_id: str) -> None:
        await tabs.add_pane(pane)
        tabs.active = f"tab-{workspace_id}"

    def action_new_agent(self) -> None:
        """Ctrl+N — 新建 Agent（循环选择角色）"""
        # 简单实现：弹出角色选择通知，后续可升级为 Modal
        self.notify("新建 Agent：输入 /new <role> 指定角色", title="新建 Agent")

    def action_close_agent(self) -> None:
        """Ctrl+W — 关闭当前 Agent"""
        active = self.app_state.get_active()
        if not active:
            return
        if len(self.app_state.workspaces) <= 1:
            self.notify("至少保留一个 Agent", severity="warning")
            return
        workspace_id = active.workspace_id
        tabs = self.query_one("#tabs", TabbedContent)
        tabs.remove_pane(f"tab-{workspace_id}")
        self.wm.close_workspace(workspace_id)
        self._update_header()

    def action_next_tab(self) -> None:
        """Ctrl+Tab — 切换到下一个 Agent"""
        tabs = self.query_one("#tabs", TabbedContent)
        # Textual TabbedContent 内置 tab 切换
        tabs.action_next_tab()

    def action_toggle_perm(self) -> None:
        """F4 — 切换权限侧边栏"""
        self.query_one("#perm-sidebar", PermissionSidebar).toggle()

    def action_show_help(self) -> None:
        """F1 — 显示帮助"""
        help_text = (
            "快捷键：\n"
            "  Ctrl+N  新建 Agent\n"
            "  Ctrl+W  关闭 Agent\n"
            "  Ctrl+Tab 切换 Agent\n"
            "  Ctrl+S  切换分屏\n"
            "  F4      权限面板\n"
            "  Ctrl+Q  退出\n\n"
            "命令：/new <role>  /close  /list  /ref <id>  /delegate <id> <task>"
        )
        self.notify(help_text, title="帮助", timeout=8)

    # ── 消息处理 ─────────────────────────────────────────────────

    def on_workspace_tab_user_input(self, event: WorkspaceTab.UserInput) -> None:
        """处理用户输入"""
        event.stop()
        text = event.text.strip()
        workspace_id = event.workspace_id

        # 命令路由
        if text.startswith("/"):
            self._handle_command(workspace_id, text)
        else:
            # 普通消息 → 调用模型
            self.run_worker(
                self._process_message(workspace_id, text),
                exclusive=False,
                name=f"chat-{workspace_id}",
            )

    def on_tabbed_content_tab_activated(self, event: TabbedContent.TabActivated) -> None:
        """标签页切换"""
        tab_id = event.tab.id or ""
        if tab_id.startswith("tab-"):
            workspace_id = tab_id[4:]
            self.wm.switch_workspace(workspace_id)
            self._update_header()

    # ── 命令处理 ─────────────────────────────────────────────────

    def _handle_command(self, workspace_id: str, text: str) -> None:
        parts = text.split(maxsplit=2)
        cmd = parts[0].lower()

        if cmd in ("/quit", "/exit", "/q"):
            self.exit()

        elif cmd == "/new":
            role = parts[1] if len(parts) > 1 else "pm"
            if role in BUILTIN_ROLES:
                self._create_workspace_tab(role)
            else:
                self._append_system_msg(workspace_id,
                    f"未知角色: {role}。可用角色: {', '.join(BUILTIN_ROLES)}")

        elif cmd == "/close":
            self.action_close_agent()

        elif cmd == "/list":
            lines = ["当前 Agent 列表："]
            for ws in self.app_state.workspace_list():
                active_mark = "★" if ws.workspace_id == self.app_state.active_workspace else " "
                lines.append(f"  {active_mark} [{ws.workspace_id}] {ws.agent_role} — {ws.task_context or '无任务'}")
            self._append_system_msg(workspace_id, "\n".join(lines))

        elif cmd == "/clear":
            ws = self.app_state.workspaces.get(workspace_id)
            if ws:
                ws.messages.clear()
                self._get_task_panel(workspace_id).clear_messages()

        elif cmd == "/ref":
            ref_id = parts[1] if len(parts) > 1 else ""
            self._handle_ref(workspace_id, ref_id)

        elif cmd == "/delegate":
            if len(parts) >= 3:
                target_id, task = parts[1], parts[2]
                self._handle_delegate(workspace_id, target_id, task)
            else:
                self._append_system_msg(workspace_id, "用法: /delegate <agent-id> <task>")

        elif cmd == "/help":
            self.action_show_help()

        elif cmd == "/perm":
            self.action_toggle_perm()

        else:
            self._append_system_msg(workspace_id, f"未知命令: {cmd}。输入 /help 查看帮助")

    def _handle_ref(self, workspace_id: str, ref_id: str) -> None:
        """引用其他 Agent 的最后输出"""
        target = self.app_state.workspaces.get(ref_id)
        if not target:
            self._append_system_msg(workspace_id, f"Agent 不存在: {ref_id}")
            return
        # 找最后一条 assistant 消息
        last_msg = next(
            (m for m in reversed(target.messages) if m.role == "assistant"), None
        )
        if not last_msg:
            self._append_system_msg(workspace_id, f"Agent {ref_id} 暂无输出")
            return
        ref_text = f"[引用自 {target.agent_role} ({ref_id})]\n{last_msg.content}"
        ws = self.app_state.workspaces.get(workspace_id)
        if ws:
            panel = self._get_task_panel(workspace_id)
            msg = ws.add_message("system", ref_text)
            panel.append_message(msg)

    def _handle_delegate(self, from_id: str, target_id: str, task: str) -> None:
        """向目标 Agent 委派任务"""
        target = self.app_state.workspaces.get(target_id)
        if not target:
            self._append_system_msg(from_id, f"Agent 不存在: {target_id}")
            return
        from_ws = self.app_state.workspaces.get(from_id)
        from_role = from_ws.agent_role if from_ws else "unknown"
        delegate_text = f"[{from_role} ({from_id}) 委派任务]\n{task}"
        panel = self._get_task_panel(target_id)
        msg = target.add_message("system", delegate_text)
        panel.append_message(msg)
        self.notify(f"任务已委派给 {target_id}", title="委派成功")

    # ── 模型调用 ─────────────────────────────────────────────────

    async def _process_message(self, workspace_id: str, text: str) -> None:
        """异步处理用户消息，流式更新 TaskPanel"""
        panel = self._get_task_panel(workspace_id)
        ws = self.app_state.workspaces.get(workspace_id)
        if not ws:
            return

        # 先在 UI 显示用户消息（send_message 内部也会 add_message，
        # 所以这里手动构造一个临时 Message 对象用于显示）
        from tui.state import Message
        from datetime import datetime
        user_display = Message(
            id=f"{workspace_id}-ui-{len(ws.messages)}",
            role="user",
            content=text,
        )
        panel.append_message(user_display)

        # 开始流式头部
        panel.start_stream()

        def on_chunk(chunk: str) -> None:
            panel.append_stream_chunk(chunk)

        def on_done(full: str) -> None:
            panel.end_stream(full)

        await self.wm.send_message(
            workspace_id, text,
            on_chunk=on_chunk,
            on_done=on_done,
        )
        self._update_header()

    # ── 辅助方法 ─────────────────────────────────────────────────

    def _get_task_panel(self, workspace_id: str):
        """获取指定工作区的 TaskPanel"""
        try:
            ws_widget = self.query_one(f"#ws-{workspace_id}", WorkspaceTab)
            return ws_widget.split_view.task_panel
        except NoMatches:
            # 返回一个空操作对象
            class _Noop:
                def append_message(self, *a, **k): pass
                def start_stream(self): pass
                def append_stream_chunk(self, *a): pass
                def end_stream(self, *a): pass
                def clear_messages(self): pass
            return _Noop()

    def _append_system_msg(self, workspace_id: str, text: str) -> None:
        ws = self.app_state.workspaces.get(workspace_id)
        if ws:
            msg = ws.add_message("system", text)
            self._get_task_panel(workspace_id).append_message(msg)

    def _update_header(self) -> None:
        try:
            header = self.query_one("#header", ADDSHeader)
            header.agent_count = self.app_state.agent_count
            header.total_tokens = self.app_state.total_tokens
            header.perm_mode = self.app_state.permission_mode
            if self._model:
                header.model_name = self._model.get_model_name()
                header.context_window = self._model.get_context_window()
        except NoMatches:
            pass
