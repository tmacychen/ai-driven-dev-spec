"""
CommandPalette — 命令面板

Ctrl+P 触发，列出所有菜单操作，支持模糊搜索后执行。
"""

from __future__ import annotations

from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Vertical
from textual.screen import ModalScreen
from textual.widgets import Input, Static


# ---------------------------------------------------------------------------
# 所有可执行命令的完整列表
# ---------------------------------------------------------------------------

ALL_COMMANDS: list[dict] = [
    # Agent
    {"label": "New Agent...",              "group": "Agent",      "action": "new_agent",      "payload": ""},
    {"label": "Close Agent",               "group": "Agent",      "action": "close_agent",    "payload": ""},
    {"label": "List Roles",                "group": "Agent",      "action": "list_roles",     "payload": ""},
    {"label": "Agent Status",              "group": "Agent",      "action": "agent_status",   "payload": ""},
    # View
    {"label": "Toggle Split View",         "group": "View",       "action": "toggle_split",   "payload": ""},
    {"label": "Toggle Permission Sidebar", "group": "View",       "action": "toggle_perm",    "payload": ""},
    {"label": "Help",                      "group": "View",       "action": "show_help",      "payload": ""},
    # Skin
    {"label": "Skin: Default",             "group": "Skin",       "action": "switch_skin",    "payload": "default"},
    {"label": "Skin: Cyberpunk",           "group": "Skin",       "action": "switch_skin",    "payload": "cyberpunk"},
    {"label": "Skin: Matrix",              "group": "Skin",       "action": "switch_skin",    "payload": "matrix"},
    {"label": "Skin: Nordic",              "group": "Skin",       "action": "switch_skin",    "payload": "nordic"},
    {"label": "Skin: Sakura",              "group": "Skin",       "action": "switch_skin",    "payload": "sakura"},
    {"label": "Skin: Skynet",              "group": "Skin",       "action": "switch_skin",    "payload": "skynet"},
    {"label": "Skin: Vault-Tec",           "group": "Skin",       "action": "switch_skin",    "payload": "vault-tec"},
    # App
    {"label": "About ADDS",                "group": "App",        "action": "about",          "payload": ""},
    {"label": "Quit",                      "group": "App",        "action": "quit",           "payload": ""},
]


def _fuzzy_match(query: str, text: str) -> bool:
    """简单模糊匹配：query 中每个字符按顺序出现在 text 中"""
    if not query:
        return True
    text_lower = text.lower()
    query_lower = query.lower()
    idx = 0
    for ch in query_lower:
        pos = text_lower.find(ch, idx)
        if pos == -1:
            return False
        idx = pos + 1
    return True


class CommandItem(Static):
    """单个命令条目"""

    DEFAULT_CSS = """
    CommandItem {
        height: 1;
        padding: 0 2;
        color: $foreground;
        background: transparent;
    }
    CommandItem:hover {
        background: $accent 40%;
    }
    CommandItem.--selected {
        background: $accent;
        color: $text;
    }
    """

    def __init__(self, cmd: dict, **kwargs) -> None:
        super().__init__(**kwargs)
        self._cmd = cmd
        group = cmd["group"]
        label = cmd["label"]
        self.update(f"[dim]{group}[/dim]  {label}")

    @property
    def cmd(self) -> dict:
        return self._cmd

    def on_click(self) -> None:
        self.app.pop_screen()
        self._execute()

    def _execute(self) -> None:
        action = self._cmd["action"]
        payload = self._cmd["payload"]
        if action == "quit":
            self.app.exit()
        else:
            method = getattr(self.app, f"action_{action}", None)
            if method:
                method(payload) if payload else method()
            else:
                self.app.notify(f"未知操作: {action}", severity="warning")


class CommandPalette(ModalScreen):
    """命令面板 — 模糊搜索所有菜单操作"""

    DEFAULT_CSS = """
    CommandPalette {
        align: center top;
    }
    CommandPalette > #palette-box {
        width: 60;
        height: auto;
        max-height: 30;
        background: $surface;
        border: solid $accent 80%;
        margin-top: 3;
    }
    CommandPalette #palette-title {
        height: 1;
        background: $accent 20%;
        color: $accent;
        padding: 0 2;
        text-style: bold;
    }
    CommandPalette #palette-input {
        height: 3;
        border: none;
        border-bottom: solid $primary 40%;
        background: $surface;
        padding: 0 1;
    }
    CommandPalette #palette-results {
        height: auto;
        max-height: 22;
        overflow-y: auto;
    }
    CommandPalette #palette-empty {
        height: 2;
        padding: 0 2;
        color: $foreground 40%;
        content-align: left middle;
    }
    """

    BINDINGS = [
        Binding("escape", "close", show=False),
        Binding("up",     "move_up",   show=False),
        Binding("down",   "move_down", show=False),
        Binding("enter",  "execute",   show=False),
    ]

    def __init__(self, **kwargs) -> None:
        super().__init__(**kwargs)
        self._selected: int = 0
        self._filtered: list[dict] = list(ALL_COMMANDS)

    def compose(self) -> ComposeResult:
        with Vertical(id="palette-box"):
            yield Static("⌘ 命令面板  (输入搜索，↑↓ 选择，Enter 执行，Esc 关闭)", id="palette-title")
            yield Input(placeholder="搜索命令…", id="palette-input")
            with Vertical(id="palette-results"):
                for cmd in self._filtered:
                    yield CommandItem(cmd)

    def on_mount(self) -> None:
        self.query_one("#palette-input", Input).focus()
        self._highlight(0)

    def on_input_changed(self, event: Input.Changed) -> None:
        query = event.value.strip()
        self._filtered = [c for c in ALL_COMMANDS if _fuzzy_match(query, c["label"] + " " + c["group"])]
        self._selected = 0
        self._rebuild_results()

    def _rebuild_results(self) -> None:
        results = self.query_one("#palette-results", Vertical)
        results.remove_children()
        if not self._filtered:
            results.mount(Static("无匹配命令", id="palette-empty"))
        else:
            for cmd in self._filtered:
                results.mount(CommandItem(cmd))
            self._highlight(0)

    def _highlight(self, idx: int) -> None:
        items = list(self.query(CommandItem))
        if not items:
            return
        self._selected = max(0, min(idx, len(items) - 1))
        for i, item in enumerate(items):
            if i == self._selected:
                item.add_class("--selected")
            else:
                item.remove_class("--selected")

    def action_move_up(self) -> None:
        self._highlight(self._selected - 1)

    def action_move_down(self) -> None:
        self._highlight(self._selected + 1)

    def action_execute(self) -> None:
        items = list(self.query(CommandItem))
        if items and 0 <= self._selected < len(items):
            self.app.pop_screen()
            items[self._selected]._execute()

    def action_close(self) -> None:
        self.app.pop_screen()
