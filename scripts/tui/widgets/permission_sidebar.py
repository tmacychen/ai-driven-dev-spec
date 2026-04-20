"""
PermissionSidebar 组件 — 非打断式权限确认侧边栏

跨所有 Agent 的权限请求队列，标记来源 Workspace
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Callable, Dict, List, Optional

from textual.app import ComposeResult
from textual.message import Message as TMessage
from textual.reactive import reactive
from textual.widget import Widget
from textual.widgets import Button, Label, Static


@dataclass
class PermRequest:
    """权限请求"""
    req_id: str
    workspace_id: str
    tool: str
    command: str
    callback: Optional[Callable[[bool], None]] = None


class PermissionSidebar(Widget):
    """权限侧边栏"""

    DEFAULT_CSS = """
    PermissionSidebar {
        width: 28;
        height: 1fr;
        border-left: solid $error 40%;
        background: $surface;
        display: none;
    }
    PermissionSidebar.visible {
        display: block;
    }
    PermissionSidebar #perm-title {
        height: 1;
        background: $error 30%;
        color: $foreground;
        padding: 0 1;
        content-align: left middle;
    }
    PermissionSidebar .perm-item {
        height: auto;
        border-bottom: solid $panel 80%;
        padding: 0 1;
        margin: 0;
    }
    PermissionSidebar .perm-cmd {
        color: $warning;
        text-style: bold;
    }
    PermissionSidebar .perm-source {
        color: $foreground 60%;
    }
    PermissionSidebar .perm-buttons {
        height: 1;
        layout: horizontal;
    }
    PermissionSidebar Button {
        height: 1;
        min-width: 6;
        margin: 0 1 0 0;
    }
    """

    # 消息：用户做出权限决策
    class Decision(TMessage):
        def __init__(self, req_id: str, allowed: bool, always: bool = False) -> None:
            super().__init__()
            self.req_id = req_id
            self.allowed = allowed
            self.always = always

    _requests: List[PermRequest]

    def __init__(self, **kwargs) -> None:
        super().__init__(**kwargs)
        self._requests = []

    def compose(self) -> ComposeResult:
        yield Static("🔒 权限请求 (0)", id="perm-title")
        yield Static("", id="perm-list")

    # ── 公共 API ─────────────────────────────────────────────────

    def add_request(self, req: PermRequest) -> None:
        self._requests.append(req)
        self.add_class("visible")
        self._refresh()

    def remove_request(self, req_id: str) -> None:
        self._requests = [r for r in self._requests if r.req_id != req_id]
        if not self._requests:
            self.remove_class("visible")
        self._refresh()

    def toggle(self) -> None:
        if "visible" in self.classes:
            self.remove_class("visible")
        else:
            if self._requests:
                self.add_class("visible")

    # ── 内部 ─────────────────────────────────────────────────────

    def _refresh(self) -> None:
        title = self.query_one("#perm-title", Static)
        title.update(f"🔒 权限请求 ({len(self._requests)})")
        # 重新挂载请求列表（简化实现）
        perm_list = self.query_one("#perm-list", Static)
        lines = []
        for req in self._requests[:5]:  # 最多显示 5 条
            lines.append(f"[{req.workspace_id}] [{req.tool}]")
            lines.append(f"  {req.command[:24]}")
            lines.append("  [允许] [拒绝]")
            lines.append("")
        perm_list.update("\n".join(lines))

    def on_button_pressed(self, event: Button.Pressed) -> None:
        btn_id = event.button.id or ""
        if "-allow-" in btn_id or "-deny-" in btn_id:
            parts = btn_id.split("-")
            action = parts[0]   # allow / deny
            req_id = "-".join(parts[2:])
            allowed = action == "allow"
            self.post_message(self.Decision(req_id=req_id, allowed=allowed))
            self.remove_request(req_id)
