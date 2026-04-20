"""
WorkspaceTab 组件 — 单个 Agent 工作区标签页

每个标签页 = 独立的 Agent 实例
包含：SplitView（TaskPanel + 可选 ReferencePanel）+ InputArea
"""

from __future__ import annotations

from textual.app import ComposeResult
from textual.binding import Binding
from textual.message import Message as TMessage
from textual.widget import Widget

from tui.state import WorkspaceState
from tui.widgets.input_area import InputArea
from tui.widgets.split_view import SplitView


class WorkspaceTab(Widget):
    """Agent 工作区标签页"""

    DEFAULT_CSS = """
    WorkspaceTab {
        width: 1fr;
        height: 1fr;
        layout: vertical;
    }
    WorkspaceTab SplitView {
        height: 1fr;
    }
    WorkspaceTab InputArea {
        height: auto;
        max-height: 8;
    }
    """

    BINDINGS = [
        Binding("ctrl+s", "toggle_split", "分屏", show=True),
    ]

    # 消息：用户提交输入（冒泡到 App）
    class UserInput(TMessage):
        def __init__(self, workspace_id: str, text: str) -> None:
            super().__init__()
            self.workspace_id = workspace_id
            self.text = text

    def __init__(self, workspace: WorkspaceState, **kwargs) -> None:
        super().__init__(**kwargs)
        self.workspace = workspace

    def compose(self) -> ComposeResult:
        yield SplitView(workspace_id=self.workspace.workspace_id, id="split-view")
        yield InputArea(id="input-area")

    def on_mount(self) -> None:
        self.query_one("#input-area", InputArea).focus_input()

    def on_input_area_submitted(self, event: InputArea.Submitted) -> None:
        """InputArea 提交 → 冒泡到 App"""
        event.stop()
        self.post_message(self.UserInput(
            workspace_id=self.workspace.workspace_id,
            text=event.text,
        ))

    def action_toggle_split(self) -> None:
        sv = self.query_one("#split-view", SplitView)
        sv.toggle_split()
        self.workspace.split_enabled = sv.split_enabled

    def on_activate(self) -> None:
        """标签页激活时恢复焦点"""
        self.query_one("#input-area", InputArea).focus_input()

    @property
    def split_view(self) -> SplitView:
        return self.query_one("#split-view", SplitView)

    @property
    def input_area(self) -> InputArea:
        return self.query_one("#input-area", InputArea)
