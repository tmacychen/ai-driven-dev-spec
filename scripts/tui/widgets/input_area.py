"""
InputArea 组件 — 多行输入区域

支持：多行编辑、历史记录（↑/↓）、命令补全（Tab）、Ctrl+Enter 发送
"""

from __future__ import annotations

from collections import deque
from typing import Callable, Deque, List, Optional

from textual.app import ComposeResult
from textual.binding import Binding
from textual.message import Message as TMessage
from textual.reactive import reactive
from textual.widget import Widget
from textual.widgets import TextArea, Static


class InputArea(Widget):
    """底部多行输入区域"""

    DEFAULT_CSS = """
    InputArea {
        height: auto;
        max-height: 8;
        border-top: solid $primary 50%;
        background: $surface;
    }
    InputArea TextArea {
        height: auto;
        max-height: 6;
        border: none;
        background: $surface;
        padding: 0 1;
    }
    InputArea #input-hint {
        height: 1;
        color: $foreground 50%;
        padding: 0 1;
        content-align: left middle;
    }
    """

    BINDINGS = [
        Binding("ctrl+enter", "submit", "发送", show=True),
        Binding("escape", "clear_input", "清空", show=False),
        Binding("up", "history_prev", "上一条", show=False),
        Binding("down", "history_next", "下一条", show=False),
    ]

    # 消息：用户提交输入
    class Submitted(TMessage):
        def __init__(self, text: str) -> None:
            super().__init__()
            self.text = text

    _history: Deque[str]
    _history_idx: int

    def __init__(self, **kwargs) -> None:
        super().__init__(**kwargs)
        self._history = deque(maxlen=100)
        self._history_idx = -1
        self._saved_draft = ""

    def compose(self) -> ComposeResult:
        yield TextArea(id="input-textarea", language="markdown")
        yield Static(
            "[Ctrl+Enter] 发送  [Esc] 清空  [↑/↓] 历史  [Ctrl+N] 新建Agent",
            id="input-hint",
        )

    def get_text(self) -> str:
        return self.query_one("#input-textarea", TextArea).text

    def set_text(self, text: str) -> None:
        ta = self.query_one("#input-textarea", TextArea)
        ta.clear()
        ta.insert(text)

    def clear(self) -> None:
        self.query_one("#input-textarea", TextArea).clear()
        self._history_idx = -1

    def focus_input(self) -> None:
        self.query_one("#input-textarea", TextArea).focus()

    # ── Actions ─────────────────────────────────────────────────

    def action_submit(self) -> None:
        text = self.get_text().strip()
        if not text:
            return
        self._history.appendleft(text)
        self._history_idx = -1
        self.clear()
        self.post_message(self.Submitted(text))

    def action_clear_input(self) -> None:
        self.clear()

    def action_history_prev(self) -> None:
        if not self._history:
            return
        if self._history_idx == -1:
            self._saved_draft = self.get_text()
        self._history_idx = min(self._history_idx + 1, len(self._history) - 1)
        self.set_text(self._history[self._history_idx])

    def action_history_next(self) -> None:
        if self._history_idx <= 0:
            self._history_idx = -1
            self.set_text(self._saved_draft)
            return
        self._history_idx -= 1
        self.set_text(self._history[self._history_idx])
