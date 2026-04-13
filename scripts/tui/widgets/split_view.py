"""
SplitView 组件 — 可选分屏容器

支持：单面板 / 左右分屏，Ctrl+S 切换
"""

from __future__ import annotations

from textual.app import ComposeResult
from textual.reactive import reactive
from textual.widget import Widget

from tui.widgets.task_panel import TaskPanel
from tui.widgets.reference_panel import ReferencePanel


class SplitView(Widget):
    """分屏容器：主任务面板 + 可选参考面板"""

    DEFAULT_CSS = """
    SplitView {
        width: 1fr;
        height: 1fr;
        layout: horizontal;
    }
    SplitView TaskPanel {
        width: 1fr;
    }
    SplitView.split TaskPanel {
        width: 3fr;
    }
    SplitView.split ReferencePanel {
        width: 2fr;
    }
    SplitView:not(.split) ReferencePanel {
        display: none;
    }
    """

    split_enabled: reactive[bool] = reactive(False)

    def __init__(self, workspace_id: str = "", **kwargs) -> None:
        super().__init__(**kwargs)
        self.workspace_id = workspace_id

    def compose(self) -> ComposeResult:
        yield TaskPanel(workspace_id=self.workspace_id, id="task-panel")
        yield ReferencePanel(id="ref-panel")

    def watch_split_enabled(self, value: bool) -> None:
        if value:
            self.add_class("split")
        else:
            self.remove_class("split")

    def toggle_split(self) -> None:
        self.split_enabled = not self.split_enabled

    @property
    def task_panel(self) -> TaskPanel:
        return self.query_one("#task-panel", TaskPanel)

    @property
    def ref_panel(self) -> ReferencePanel:
        return self.query_one("#ref-panel", ReferencePanel)
