"""
ShortcutBar — 底部快捷键提示栏（浮动风格）

替代 Textual 默认 Footer，显示常用快捷键。
"""

from __future__ import annotations

from textual.app import ComposeResult
from textual.widget import Widget
from textual.widgets import Static

# 快捷键定义：(按键, 说明)
SHORTCUTS = [
    ("^S", "分屏"),
    ("^N", "新建"),
    ("^W", "关闭"),
    ("^P", "权限"),
    ("^H", "帮助"),
    ("^Q", "退出"),
]


class ShortcutBar(Widget):
    """底部快捷键浮动提示栏"""

    DEFAULT_CSS = """
    ShortcutBar {
        dock: bottom;
        height: 1;
        background: $primary 15%;
        layout: horizontal;
        padding: 0 1;
        color: $foreground 60%;
    }
    ShortcutBar Static {
        width: 1fr;
        content-align: left middle;
    }
    """

    def compose(self) -> ComposeResult:
        # 构建快捷键提示文本，用 Rich markup 高亮按键部分
        segments = []
        for key, desc in SHORTCUTS:
            segments.append(f"[bold $accent]{key}[/] {desc}")
        line = "  [dim]|[/]  ".join(segments)
        yield Static(line, markup=True)
