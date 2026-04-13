"""
ReferencePanel 组件 — 分屏参考资料面板（只读）

用于显示：文件内容、API 文档、其他 Agent 的输出
"""

from __future__ import annotations

from textual.app import ComposeResult
from textual.widget import Widget
from textual.widgets import RichLog, Static


class ReferencePanel(Widget):
    """参考资料面板（分屏右侧）"""

    DEFAULT_CSS = """
    ReferencePanel {
        width: 1fr;
        height: 1fr;
        border-left: solid $primary 30%;
    }
    ReferencePanel #ref-title {
        height: 1;
        background: $primary 20%;
        color: $foreground;
        padding: 0 1;
        content-align: left middle;
    }
    ReferencePanel RichLog {
        width: 1fr;
        height: 1fr;
        background: $surface;
        padding: 0 1;
    }
    """

    def __init__(self, title: str = "参考资料", **kwargs) -> None:
        super().__init__(**kwargs)
        self._title = title

    def compose(self) -> ComposeResult:
        yield Static(f"📄 {self._title}", id="ref-title")
        yield RichLog(id="ref-log", highlight=True, markup=True, wrap=True)

    def set_title(self, title: str) -> None:
        self._title = title
        self.query_one("#ref-title", Static).update(f"📄 {title}")

    def set_content(self, content: str, title: str = "") -> None:
        """设置参考内容"""
        if title:
            self.set_title(title)
        log = self.query_one("#ref-log", RichLog)
        log.clear()
        log.write(content, markup=False)

    def append_content(self, content: str) -> None:
        self.query_one("#ref-log", RichLog).write(content, markup=False)

    def clear(self) -> None:
        self.query_one("#ref-log", RichLog).clear()
