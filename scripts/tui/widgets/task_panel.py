"""
TaskPanel 组件 — Agent 主工作区

显示对话历史，支持 Markdown 渲染、流式更新、消息折叠
"""

from __future__ import annotations

from typing import List, Optional

from textual.app import ComposeResult
from textual.reactive import reactive
from textual.scroll_view import ScrollView
from textual.widget import Widget
from textual.widgets import Markdown, Static, RichLog

from tui.state import Message, WorkspaceState
from tui.skin_adapter import role_icon


# 角色显示配置
_ROLE_PREFIX = {
    "user":      ("👤", "bold"),
    "assistant": ("🤖", ""),
    "system":    ("⚙️ ", "dim"),
    "tool":      ("🔧", "dim"),
}


def _format_message(msg: Message) -> str:
    """将 Message 格式化为 Rich markup 字符串"""
    icon, style = _ROLE_PREFIX.get(msg.role, ("•", ""))
    role_label = msg.role.upper()
    content = msg.content

    # 折叠长消息
    if msg.collapsed and len(content) > 200:
        content = content[:200] + "…[dim] (点击展开)[/dim]"

    prefix = f"[{style}]{icon} {role_label}[/]" if style else f"{icon} {role_label}"
    return f"{prefix}\n{content}\n"


class TaskPanel(Widget):
    """任务面板 — 对话历史 + 流式响应"""

    DEFAULT_CSS = """
    TaskPanel {
        width: 1fr;
        height: 1fr;
        border: none;
        overflow-y: auto;
    }
    TaskPanel RichLog {
        width: 1fr;
        height: 1fr;
        background: $background;
        padding: 0 1;
        scrollbar-gutter: stable;
    }
    TaskPanel #streaming-indicator {
        height: 1;
        color: $accent;
        padding: 0 1;
    }
    """

    streaming: reactive[bool] = reactive(False)

    def __init__(self, workspace_id: str = "", **kwargs) -> None:
        super().__init__(**kwargs)
        self.workspace_id = workspace_id
        self._stream_buffer: List[str] = []

    def compose(self) -> ComposeResult:
        yield RichLog(id="message-log", highlight=True, markup=True, wrap=True)
        yield Static("", id="streaming-indicator")

    def watch_streaming(self, value: bool) -> None:
        indicator = self.query_one("#streaming-indicator", Static)
        indicator.update("⠋ 生成中…" if value else "")

    # ── 公共 API ─────────────────────────────────────────────────

    def render_messages(self, messages: List[Message]) -> None:
        """全量渲染消息列表"""
        log = self.query_one("#message-log", RichLog)
        log.clear()
        for msg in messages:
            self._write_message(log, msg)

    def append_message(self, msg: Message) -> None:
        """追加单条消息"""
        log = self.query_one("#message-log", RichLog)
        self._write_message(log, msg)

    def start_stream(self) -> None:
        """开始流式输出"""
        self._stream_buffer = []
        self.streaming = True
        log = self.query_one("#message-log", RichLog)
        log.write("🤖 ASSISTANT\n", markup=True)

    def append_stream_chunk(self, chunk: str) -> None:
        """追加流式片段（节流由调用方控制）"""
        self._stream_buffer.append(chunk)
        log = self.query_one("#message-log", RichLog)
        log.write(chunk, markup=False)

    def end_stream(self, full_content: str) -> None:
        """结束流式输出"""
        self.streaming = False
        self._stream_buffer = []
        log = self.query_one("#message-log", RichLog)
        log.write("\n", markup=False)

    def clear_messages(self) -> None:
        self.query_one("#message-log", RichLog).clear()

    # ── 内部 ─────────────────────────────────────────────────────

    def _write_message(self, log: RichLog, msg: Message) -> None:
        icon, style = _ROLE_PREFIX.get(msg.role, ("•", ""))
        role_label = msg.role.upper()

        if style:
            log.write(f"[{style}]{icon} {role_label}[/{style}]", markup=True)
        else:
            log.write(f"{icon} {role_label}", markup=True)

        content = msg.content
        if msg.collapsed and len(content) > 300:
            content = content[:300] + "…"

        log.write(content, markup=False)

        if msg.thinking:
            log.write(f"[dim]💭 {msg.thinking[:100]}…[/dim]", markup=True)

        log.write("─" * 40, markup=False)
