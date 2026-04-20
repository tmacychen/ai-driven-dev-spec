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

import re


def _sanitize_display(content: str) -> str:
    """
    清理 LLM 输出中的内部结构标签，使 UI 显示友好

    处理规则：
    1. <agent><agent_type>...</agent_type><description>...</description><path>...</path></agent>
       → 折叠为 [Agent: type] 描述摘要
    2. <read /><glob /> 等工具调用标签 → 折叠为 [工具名] 一行
    3. <thinking> 块 → 已由 thinking 回调处理，这里不重复显示
    4. 保留纯文本内容不变
    """
    import textwrap
    result = content

    # ── 1. 折叠 <agent> 块 ──────────────────────────────────────
    def _collapse_agent(m):
        inner = m.group(0)
        # 提取类型和描述
        type_match = re.search(r'<agent_type>([^<]+)</agent_type>', inner)
        desc_match = re.search(r'<description>([^<]+)</description>', inner)
        atype = type_match.group(1).strip() if type_match else "Agent"
        desc = desc_match.group(1).strip() if desc_match else ""
        if desc:
            desc = textwrap.shorten(desc, width=80, placeholder="…")
            return f"[bold #6B7280]▸ {atype}[/] {desc}"
        return f"[bold #6B7280]▸ {atype}[/]"
    result = re.sub(r'<agent>\s*<agent_type>.*?</agent>', _collapse_agent,
                    result, flags=re.DOTALL)

    # ── 2. 折叠单行工具标签 <read /> <glob /> 等 ─────────────────
    def _collapse_tool_tag(m):
        tag_name = m.group(1)
        attrs_str = m.group(2) or ""
        # 提取关键属性值（file_path, pattern 等）
        key_attrs = []
        for attr in ["file_path", "pattern", "query", "url", "command"]:
            am = re.search(rf'{attr}=([\'"])([^\\1]*?)\1', attrs_str)
            if am:
                val = textwrap.shorten(am.group(2), width=50, placeholder="…")
                key_attrs.append(f"{attr}={val}")
                break
        detail = ", ".join(key_attrs[:2]) if key_attrs else ""
        if detail:
            return f"[dim #6B7280]▸ 🔧 {tag_name}[/] ({detail})"
        return f"[dim #6B7280]▸ 🔧 {tag_name}[/]"
    result = re.sub(
        r'<(\w+?)(?:\s+([^/>]*?))?/?>', _collapse_tool_tag, result
    )

    # ── 3. 清理残留闭合标签 ────────────────────────────────────
    result = re.sub(r'</(?:agent|agent_type|description|path|thinking)>', '', result)

    # ── 4. 清理多余空行（但保留段落间距）─────────────────────────
    result = re.sub(r'\n{3,}', '\n\n', result)

    return result.strip()


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
        background: $surface;
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
        self._thinking_buffer: List[str] = []
        self._tool_call_shown: bool = False

    def compose(self) -> ComposeResult:
        yield RichLog(id="message-log", highlight=True, markup=True, wrap=True)
        yield Static("", id="streaming-indicator")

    def watch_streaming(self, value: bool) -> None:
        indicator = self.query_one("#streaming-indicator", Static)
        if value:
            indicator.update("⠋ 生成中…")
        # 结束时由 end_stream 负责清空，这里不重复清空

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
        self._thinking_buffer = []
        self._tool_call_shown = False
        self.streaming = True
        # 写入 ASSISTANT 标题行
        log = self.query_one("#message-log", RichLog)
        from rich.text import Text
        log.write(Text("🤖 ASSISTANT", style="bold"))

    # ── 状态映射：Agent Loop 各阶段对应的 UI 提示 ──
    _STATUS_DISPLAY = {
        "thinking":  "🧠 思考中…",
        "streaming": "⠋ 生成中…",
        "tool_call": "🔧 调用工具…",
        "executing": "⚙️ 执行中…",
        "waiting":   "⏳ 等待模型…",
        "idle":      "",
    }

    def update_status(self, status: str) -> None:
        """更新 Agent Loop 状态指示器"""
        indicator = self.query_one("#streaming-indicator", Static)
        display = self._STATUS_DISPLAY.get(status, status)
        indicator.update(display)
        log.write(Text("🤖 ASSISTANT", style="bold"))

    def append_thinking_chunk(self, chunk: str, is_first: bool = False) -> None:
        """
        追加 LLM 思考过程片段（实时显示，不占主要聊天区域）

        is_first=True 时写入标题行，之后追加内容
        """
        from rich.text import Text
        log = self.query_one("#message-log", RichLog)
        self._thinking_buffer.append(chunk)
        total = sum(len(c) for c in self._thinking_buffer)

        if is_first:
            # 首次 thinking：写入紧凑的标题行（在 ASSISTANT 行之后）
            thinking_header = Text("  🧠 思考中… ", style="dim bold #B8860B")
            log.write(thinking_header)
            # 更新 streaming 指示器
            indicator = self.query_one("#streaming-indicator", Static)
            indicator.update(f"🧠 思考 ({total} 字)")

        # 实时更新指示器
        indicator = self.query_one("#streaming-indicator", Static)
        indicator.update(f"🧠 思考 ({total} 字)")

    def show_tool_call(self, tool_name: str, args: dict) -> None:
        """
        在 UI 显示 LLM 触发的工具调用
        """
        if self._tool_call_shown:
            return
        self._tool_call_shown = True
        from rich.text import Text
        log = self.query_one("#message-log", RichLog)
        # 显示关键参数（截断过长内容）
        display_args = {
            k: (str(v)[:80] + "…" if len(str(v)) > 80 else str(v))
            for k, v in (args.items() if isinstance(args, dict) else {})
        }
        tool_label = Text(f"  🔧 工具: {tool_name}", style="dim #6B7280")
        log.write(tool_label)
        # 更新指示器
        indicator = self.query_one("#streaming-indicator", Static)
        indicator.update(f"🔧 {tool_name}")

    def append_stream_chunk(self, chunk: str) -> None:
        """追加流式片段 — 缓冲，不逐 chunk 写入 RichLog（避免每 chunk 换行）"""
        self._stream_buffer.append(chunk)
        # 实时更新 streaming indicator 显示已收到的字数
        indicator = self.query_one("#streaming-indicator", Static)
        total = sum(len(c) for c in self._stream_buffer)
        indicator.update(f"⠋ 生成中… ({total} 字)")

    def end_stream(self, full_content: str) -> None:
        """结束流式输出 — 一次性将完整内容写入 RichLog"""
        self.streaming = False
        self._stream_buffer = []
        log = self.query_one("#message-log", RichLog)

        # 思考摘要（如果有积累的 thinking 内容）
        if self._thinking_buffer:
            full_thinking = "".join(self._thinking_buffer)
            from rich.text import Text
            first_line = full_thinking.split("\n")[0][:100]
            log.write(Text(f"  💭 {first_line}{'…' if len(full_thinking) > 100 else ''}", style="dim #B8860B"))
            self._thinking_buffer = []

        # 一次性写入完整内容（清理内部标签后显示）
        if full_content:
            display_text = _sanitize_display(full_content)
            log.write(display_text)
        log.write("─" * 40)
        indicator = self.query_one("#streaming-indicator", Static)
        indicator.update("")

    def clear_messages(self) -> None:
        self.query_one("#message-log", RichLog).clear()

    # ── 内部 ─────────────────────────────────────────────────────

    def _write_message(self, log: RichLog, msg: Message) -> None:
        icon, style = _ROLE_PREFIX.get(msg.role, ("•", ""))
        role_label = msg.role.upper()

        # Textual 8.x RichLog.write() 不接受 markup 参数
        # 用 Text 对象传递样式
        from rich.text import Text

        header = Text()
        if style:
            header.append(f"{icon} {role_label}", style=style)
        else:
            header.append(f"{icon} {role_label}")
        log.write(header)

        content = msg.content
        if msg.collapsed and len(content) > 300:
            content = content[:300] + "…"
        # 清理内部结构标签，使显示友好
        display_content = _sanitize_display(content)
        log.write(display_content)

        if msg.thinking:
            thinking_text = Text(f"💭 {msg.thinking[:100]}…", style="dim")
            log.write(thinking_text)

        log.write("─" * 40)
