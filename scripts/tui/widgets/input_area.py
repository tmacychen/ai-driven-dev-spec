"""
InputArea 组件 — 多行输入区域

交互方式（无系统快捷键冲突）：
- 鼠标点击 [发送] 按钮
- Tab 键切换焦点到 [发送] 按钮，Enter 激活
- TextArea 内 Enter 换行，Shift+Enter 也换行
"""

from __future__ import annotations

from collections import deque
from typing import Deque

from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Horizontal, Vertical
from textual.message import Message as TMessage
from textual.widget import Widget
from textual.widgets import Button, Static, TextArea


class InputArea(Widget):
    """底部输入区域：TextArea + 可点击发送按钮"""

    DEFAULT_CSS = """
    InputArea {
        height: auto;
        max-height: 10;
        border-top: solid $primary 50%;
        background: $surface;
    }
    InputArea #input-row {
        height: auto;
        layout: horizontal;
    }
    InputArea TextArea {
        height: auto;
        min-height: 3;
        max-height: 6;
        width: 1fr;
        border: none;
        background: $surface;
        padding: 0 1;
    }
    InputArea #btn-col {
        width: 12;
        height: auto;
        layout: vertical;
        padding: 0 1;
    }
    InputArea #send-btn {
        width: 10;
        height: 3;
        background: $primary;
        color: $background;
    }
    InputArea #send-btn:focus {
        background: $accent;
        border: tall $accent;
    }
    InputArea #send-btn:hover {
        background: $accent;
    }
    InputArea #input-hint {
        height: 1;
        color: $foreground 40%;
        padding: 0 1;
        content-align: left middle;
    }
    """

    # 不绑定任何可能冲突的系统快捷键
    # 发送完全依赖：鼠标点击 / Tab→Enter
    BINDINGS = [
        Binding("escape", "clear_input", "清空", show=False),
    ]

    class Submitted(TMessage):
        def __init__(self, text: str) -> None:
            super().__init__()
            self.text = text

    def __init__(self, **kwargs) -> None:
        super().__init__(**kwargs)
        self._history: Deque[str] = deque(maxlen=100)
        self._history_idx = -1
        self._saved_draft = ""

    def compose(self) -> ComposeResult:
        with Horizontal(id="input-row"):
            yield TextArea(id="input-textarea", language="markdown")
            with Vertical(id="btn-col"):
                yield Button("发送", id="send-btn", variant="primary")
        yield Static(
            "Tab → [发送] → Enter 发送  |  鼠标点击[发送]  |  Esc 清空",
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

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "send-btn":
            event.stop()
            self._do_submit()

    def action_clear_input(self) -> None:
        self.clear()
        self.focus_input()

    def _do_submit(self) -> None:
        text = self.get_text().strip()
        if not text:
            self.focus_input()
            return
        self._history.appendleft(text)
        self._history_idx = -1
        self.clear()
        self.focus_input()
        self.post_message(self.Submitted(text))
