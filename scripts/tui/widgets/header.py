"""
Header 组件 — 顶部状态栏

显示：ADDS [N Agents] [model] [perm-mode]  Total: 45K/128K
"""

from __future__ import annotations

from textual.app import ComposeResult
from textual.reactive import reactive
from textual.widget import Widget
from textual.widgets import Static


class ADDSHeader(Widget):
    """顶部状态栏"""

    DEFAULT_CSS = """
    ADDSHeader {
        height: 1;
        background: $primary 20%;
        color: $text;
        dock: top;
    }
    ADDSHeader Static {
        width: 1fr;
        content-align: center middle;
    }
    ADDSHeader #header-left {
        width: auto;
        padding: 0 1;
        content-align: left middle;
    }
    ADDSHeader #header-right {
        width: auto;
        padding: 0 1;
        content-align: right middle;
    }
    """

    model_name: reactive[str] = reactive("—")
    agent_count: reactive[int] = reactive(0)
    perm_mode: reactive[str] = reactive("default")
    total_tokens: reactive[int] = reactive(0)
    context_window: reactive[int] = reactive(128000)

    def compose(self) -> ComposeResult:
        yield Static("", id="header-left")
        yield Static("", id="header-center")
        yield Static("", id="header-right")

    def on_mount(self) -> None:
        self._refresh_display()

    def watch_model_name(self, _: str) -> None:
        self._refresh_display()

    def watch_agent_count(self, _: int) -> None:
        self._refresh_display()

    def watch_perm_mode(self, _: str) -> None:
        self._refresh_display()

    def watch_total_tokens(self, _: int) -> None:
        self._refresh_display()

    def _refresh_display(self) -> None:
        left = self.query_one("#header-left", Static)
        center = self.query_one("#header-center", Static)
        right = self.query_one("#header-right", Static)

        left.update(f"⚡ ADDS  [{self.agent_count} Agents]  {self.model_name}")
        center.update(f"perm: {self.perm_mode}")

        total_k = self.total_tokens // 1000
        ctx_k = self.context_window // 1000
        right.update(f"Tokens: {total_k}K/{ctx_k}K")
