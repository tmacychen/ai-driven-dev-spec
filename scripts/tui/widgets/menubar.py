"""
ADDS TUI 菜单栏组件

包含菜单数据模型、皮肤持久化工具函数及 MenuBar 相关 Widget。
"""

from __future__ import annotations

import json
import os
from dataclasses import dataclass, field


# ---------------------------------------------------------------------------
# 数据模型
# ---------------------------------------------------------------------------

@dataclass
class MenuEntry:
    """菜单条目数据模型"""
    label: str = ""
    action: str = ""
    payload: str = ""
    separator: bool = False
    submenu: str = ""   # 子菜单 ID（如 "skin"）


SKIN_NAMES: list[tuple[str, str]] = [
    ("Default",   "default"),
    ("Cyberpunk", "cyberpunk"),
    ("Matrix",    "matrix"),
    ("Nordic",    "nordic"),
    ("Sakura",    "sakura"),
    ("Skynet",    "skynet"),
    ("Vault-Tec", "vault-tec"),
]

MENU_DEFINITIONS: dict[str, list[MenuEntry]] = {
    "agent": [
        MenuEntry(label="New Agent...",  action="new_agent"),
        MenuEntry(label="Close Agent",   action="close_agent"),
        MenuEntry(separator=True),
        MenuEntry(label="List Roles",    action="list_roles"),
        MenuEntry(label="Agent Status",  action="agent_status"),
    ],
    "view": [
        MenuEntry(label="Toggle Split View",         action="toggle_split"),
        MenuEntry(label="Toggle Permission Sidebar", action="toggle_perm"),
        MenuEntry(separator=True),
        MenuEntry(label="Switch Skin ▶",             action="open_skin_submenu", submenu="skin"),
        MenuEntry(separator=True),
        MenuEntry(label="Help",                      action="show_help"),
    ],
    "app": [
        MenuEntry(label="About ADDS", action="about"),
        MenuEntry(separator=True),
        MenuEntry(label="Quit",       action="quit"),
    ],
}


# ---------------------------------------------------------------------------
# 皮肤持久化工具函数
# ---------------------------------------------------------------------------

def load_skin_setting(settings_path: str = ".ai/settings.json") -> str:
    """读取 .ai/settings.json 的 ui.skin 字段，缺失或出错时返回 'default'"""
    try:
        with open(settings_path, "r", encoding="utf-8") as f:
            data = json.load(f)
        return data.get("ui", {}).get("skin", "default") or "default"
    except (FileNotFoundError, json.JSONDecodeError, OSError):
        return "default"


def save_skin_setting(skin_name: str, settings_path: str = ".ai/settings.json") -> None:
    """将皮肤名称写入 .ai/settings.json 的 ui.skin 字段，保留其他字段（merge 而非覆盖）"""
    # 读取现有内容（若存在）
    data: dict = {}
    try:
        with open(settings_path, "r", encoding="utf-8") as f:
            data = json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        pass  # 文件不存在或格式错误时从空 dict 开始

    # 合并写入
    if "ui" not in data or not isinstance(data["ui"], dict):
        data["ui"] = {}
    data["ui"]["skin"] = skin_name

    # 确保目录存在
    dir_path = os.path.dirname(settings_path)
    if dir_path:
        os.makedirs(dir_path, exist_ok=True)

    with open(settings_path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


# ---------------------------------------------------------------------------
# Textual Widget 导入
# ---------------------------------------------------------------------------

from textual.app import ComposeResult
from textual.binding import Binding
from textual.message import Message
from textual.reactive import reactive
from textual.widget import Widget


# ---------------------------------------------------------------------------
# MenuBarItem
# ---------------------------------------------------------------------------

class MenuBarItem(Widget):
    """顶级菜单项"""
    DEFAULT_CSS = """
    MenuBarItem {
        width: auto;
        padding: 0 2;
        height: 1;
        background: transparent;
        color: $foreground;
    }
    MenuBarItem:hover {
        background: $accent 50%;
    }
    MenuBarItem.--active {
        background: $accent;
        color: $text;
    }
    """

    def __init__(self, label: str, menu_id: str, **kwargs) -> None:
        super().__init__(**kwargs)
        self._label = label
        self.menu_id = menu_id

    def render(self) -> str:
        return self._label

    def on_click(self) -> None:
        # 通知父级 MenuBar 展开此菜单
        self.post_message(MenuBar.ItemClicked(menu_id=self.menu_id, widget=self))


# ---------------------------------------------------------------------------
# MenuBar
# ---------------------------------------------------------------------------

class MenuBar(Widget):
    """水平菜单栏"""
    DEFAULT_CSS = """
    MenuBar {
        height: 1;
        background: $primary 20%;
        dock: top;
        layout: horizontal;
    }
    """

    BINDINGS = [
        Binding("alt", "activate_menu", "菜单", show=False),
    ]

    can_focus = True  # 允许 Tab 键将焦点移入菜单栏

    active_index: reactive[int] = reactive(-1)
    is_focused: reactive[bool] = reactive(False)

    class ItemClicked(Message):
        def __init__(self, menu_id: str, widget: "MenuBarItem") -> None:
            super().__init__()
            self.menu_id = menu_id
            self.widget = widget

    class OpenDropdown(Message):
        def __init__(self, menu_id: str, anchor: Widget) -> None:
            super().__init__()
            self.menu_id = menu_id
            self.anchor = anchor

    MENU_ITEMS = [
        ("Agent", "agent"),
        ("View",  "view"),
        ("App",   "app"),
    ]

    def compose(self) -> ComposeResult:
        for label, menu_id in self.MENU_ITEMS:
            yield MenuBarItem(label, menu_id=menu_id, id=f"menu-{menu_id}")

    def on_focus(self) -> None:
        """Tab 切换焦点到 MenuBar 时自动激活"""
        if not self.is_focused:
            self.action_activate_menu()

    def on_blur(self) -> None:
        """失去焦点时取消高亮"""
        self.deactivate()

    def action_activate_menu(self) -> None:
        """激活菜单栏，高亮第一个菜单项"""
        self.is_focused = True
        self.active_index = 0
        self._highlight_active()
        self.focus()

    def on_key(self, event) -> None:
        """键盘导航：左右方向键切换，Enter/Down 展开，Escape 退出"""
        key = event.key

        if not self.is_focused:
            return

        if key == "left":
            event.stop()
            self.active_index = (self.active_index - 1) % len(self.MENU_ITEMS)
            self._highlight_active()

        elif key == "right":
            event.stop()
            self.active_index = (self.active_index + 1) % len(self.MENU_ITEMS)
            self._highlight_active()

        elif key in ("enter", "down"):
            event.stop()
            if 0 <= self.active_index < len(self.MENU_ITEMS):
                _, menu_id = self.MENU_ITEMS[self.active_index]
                anchor = self.query_one(f"#menu-{menu_id}", MenuBarItem)
                self.post_message(MenuBar.OpenDropdown(menu_id=menu_id, anchor=anchor))

        elif key == "escape":
            event.stop()
            self.deactivate()

    def _highlight_active(self) -> None:
        """高亮当前激活的菜单项"""
        for i, (_, mid) in enumerate(self.MENU_ITEMS):
            item = self.query_one(f"#menu-{mid}", MenuBarItem)
            if i == self.active_index:
                item.add_class("--active")
            else:
                item.remove_class("--active")

    def on_menu_bar_item_clicked(self, event: "MenuBar.ItemClicked") -> None:
        # 高亮当前项
        for i, (_, mid) in enumerate(self.MENU_ITEMS):
            item = self.query_one(f"#menu-{mid}", MenuBarItem)
            if mid == event.menu_id:
                item.add_class("--active")
                self.active_index = i
            else:
                item.remove_class("--active")
        # 委托给 App 展开下拉菜单
        self.post_message(MenuBar.OpenDropdown(menu_id=event.menu_id, anchor=event.widget))

    def deactivate(self) -> None:
        """取消所有高亮"""
        for _, mid in self.MENU_ITEMS:
            self.query_one(f"#menu-{mid}", MenuBarItem).remove_class("--active")
        self.active_index = -1
        self.is_focused = False


# ---------------------------------------------------------------------------
# Dropdown 组件导入
# ---------------------------------------------------------------------------

from textual.screen import ModalScreen


# ---------------------------------------------------------------------------
# DropdownSeparator
# ---------------------------------------------------------------------------

class DropdownSeparator(Widget):
    """菜单分隔线"""
    DEFAULT_CSS = """
    DropdownSeparator {
        height: 1;
        border-bottom: tall $primary 30%;
    }
    """

    def render(self) -> str:
        return ""


# ---------------------------------------------------------------------------
# DropdownItem
# ---------------------------------------------------------------------------

class DropdownItem(Widget):
    """可点击的菜单条目"""
    DEFAULT_CSS = """
    DropdownItem {
        height: 1;
        padding: 0 2;
        width: auto;
        color: $foreground;
        background: transparent;
    }
    DropdownItem:hover {
        background: $accent 50%;
        color: $text;
    }
    DropdownItem.--highlighted {
        background: $accent;
        color: $text;
    }
    """

    def __init__(self, entry: "MenuEntry", **kwargs) -> None:
        super().__init__(**kwargs)
        self._entry = entry

    def render(self) -> str:
        return self._entry.label

    def on_click(self) -> None:
        action = self._entry.action
        payload = self._entry.payload

        if action == "open_skin_submenu":
            # 先关闭当前 overlay，再推入皮肤子菜单
            self.app.pop_screen()
            skin_entries = [
                MenuEntry(label=name, action="switch_skin", payload=skin_id)
                for name, skin_id in SKIN_NAMES
            ]
            self.app.push_screen(DropdownOverlay(menu_id="skin", entries=skin_entries))
        elif action == "quit":
            # Textual 内置退出，直接调用 exit()
            self.app.pop_screen()
            self.app.exit()
        else:
            self.app.pop_screen()
            # 通过 action_ 方法名动态调用
            method_name = f"action_{action}"
            method = getattr(self.app, method_name, None)
            if method is not None:
                if payload:
                    method(payload)
                else:
                    method()
            else:
                self.app.notify(f"未知操作: {action}", severity="warning")


# ---------------------------------------------------------------------------
# DropdownMenu
# ---------------------------------------------------------------------------

class DropdownMenu(Widget):
    """下拉菜单容器，支持键盘上下导航"""
    DEFAULT_CSS = """
    DropdownMenu {
        width: auto;
        min-width: 20;
        max-width: 32;
        background: $surface;
        border: solid $accent 60%;
        height: auto;
        padding: 0;
    }
    """

    can_focus = True  # 允许接收键盘事件

    def __init__(self, entries: "list[MenuEntry]", offset_x: int = 0, **kwargs) -> None:
        super().__init__(**kwargs)
        self._entries = entries
        self._offset_x = offset_x
        self._highlighted: int = -1

    def compose(self) -> ComposeResult:
        for entry in self._entries:
            if entry.separator:
                yield DropdownSeparator()
            else:
                yield DropdownItem(entry)

    def _items(self) -> "list[DropdownItem]":
        return list(self.query(DropdownItem))

    def on_key(self, event) -> None:
        items = self._items()
        if not items:
            return

        if event.key == "down":
            event.stop()
            self._highlighted = (self._highlighted + 1) % len(items)
            self._refresh_highlight(items)
        elif event.key == "up":
            event.stop()
            self._highlighted = (self._highlighted - 1) % len(items)
            self._refresh_highlight(items)
        elif event.key == "enter" and self._highlighted >= 0:
            event.stop()
            items[self._highlighted].on_click()

    def _refresh_highlight(self, items: "list[DropdownItem]") -> None:
        for i, item in enumerate(items):
            if i == self._highlighted:
                item.add_class("--highlighted")
            else:
                item.remove_class("--highlighted")


# ---------------------------------------------------------------------------
# DropdownOverlay
# ---------------------------------------------------------------------------

class DropdownOverlay(ModalScreen):
    """下拉菜单覆盖层"""
    DEFAULT_CSS = """
    DropdownOverlay {
        background: transparent;
        align: left top;
    }
    DropdownOverlay > DropdownMenu {
        margin-top: 2;
    }
    """

    # MenuBar 的菜单顺序，用于左右切换
    _MENU_ORDER = ["agent", "view", "app"]

    def __init__(self, menu_id: str, entries: "list[MenuEntry] | None" = None,
                 offset_x: int = 0, **kwargs) -> None:
        super().__init__(**kwargs)
        self._menu_id = menu_id
        self._entries = entries if entries is not None else MENU_DEFINITIONS.get(menu_id, [])
        self._offset_x = offset_x

    def compose(self) -> ComposeResult:
        yield DropdownMenu(self._entries, offset_x=self._offset_x)

    def on_mount(self) -> None:
        """挂载后将焦点给 DropdownMenu，使上下键导航生效"""
        try:
            self.query_one(DropdownMenu).focus()
        except Exception:
            pass

    def _close_and_deactivate(self) -> None:
        """关闭菜单并归还焦点"""
        self.app.pop_screen()
        try:
            self.app.query_one(MenuBar).deactivate()
        except Exception:
            pass
        try:
            active = self.app.app_state.get_active()
            if active:
                ws_widget = self.app.query_one(f"#ws-{active.workspace_id}")
                ws_widget.input_area.focus_input()
        except Exception:
            pass

    def _switch_to_menu(self, menu_id: str) -> None:
        """切换到另一个菜单（左右键）"""
        self.app.pop_screen()
        # 高亮 MenuBar 对应项
        try:
            menubar = self.app.query_one(MenuBar)
            idx = next((i for i, (_, mid) in enumerate(MenuBar.MENU_ITEMS) if mid == menu_id), 0)
            menubar.active_index = idx
            menubar._highlight_active()
        except Exception:
            pass
        self.app.push_screen(DropdownOverlay(menu_id=menu_id))

    def on_key(self, event) -> None:
        key = event.key

        if key == "escape":
            event.stop()
            self._close_and_deactivate()

        elif key == "left" and self._menu_id in self._MENU_ORDER:
            event.stop()
            idx = self._MENU_ORDER.index(self._menu_id)
            prev_id = self._MENU_ORDER[(idx - 1) % len(self._MENU_ORDER)]
            self._switch_to_menu(prev_id)

        elif key == "right" and self._menu_id in self._MENU_ORDER:
            event.stop()
            idx = self._MENU_ORDER.index(self._menu_id)
            next_id = self._MENU_ORDER[(idx + 1) % len(self._MENU_ORDER)]
            self._switch_to_menu(next_id)

    def on_click(self, event) -> None:
        # 点击透明背景区域（非菜单内）时关闭
        if event.widget is self:
            self._close_and_deactivate()


# ---------------------------------------------------------------------------
# AgentStatusScreen
# ---------------------------------------------------------------------------

from textual.widgets import Button, Static
from textual.containers import Vertical
from tui.state import WorkspaceState


class AgentStatusScreen(ModalScreen):
    """Agent 状态对话框"""

    DEFAULT_CSS = """
    AgentStatusScreen {
        align: center middle;
    }
    AgentStatusScreen > #dialog {
        width: 50;
        height: auto;
        background: $surface;
        border: double $accent;
        padding: 1 2;
    }
    AgentStatusScreen #close {
        margin-top: 1;
        width: 100%;
    }
    """

    def __init__(self, workspace: WorkspaceState, **kwargs) -> None:
        super().__init__(**kwargs)
        self._workspace = workspace

    def compose(self) -> ComposeResult:
        ws = self._workspace
        token_info = f"{ws.token_used} / {ws.token_budget}"
        status_info = ws.status.value if hasattr(ws.status, "value") else str(ws.status)

        with Vertical(id="dialog"):
            yield Static("Agent 状态")
            yield Static(f"工作区 ID：{ws.workspace_id}")
            yield Static(f"角色：{ws.agent_role}")
            yield Static(f"Token 使用：{token_info}")
            yield Static(f"状态：{status_info}")
            yield Button("关闭", id="close")

    def on_button_pressed(self, event: Button.Pressed) -> None:
        self.app.pop_screen()

    def on_key(self, event) -> None:
        if event.key == "escape":
            self.app.pop_screen()


# ---------------------------------------------------------------------------
# InfoScreen — 通用可复制信息对话框
# ---------------------------------------------------------------------------

from textual.widgets import TextArea as _TextArea


class InfoScreen(ModalScreen):
    """通用信息对话框，内容可选中复制，Escape 或按钮关闭"""

    DEFAULT_CSS = """
    InfoScreen {
        align: center middle;
    }
    InfoScreen > #dialog {
        width: 60;
        height: auto;
        max-height: 30;
        background: $surface;
        border: double $accent;
        padding: 1 2;
    }
    InfoScreen #info-title {
        text-style: bold;
        color: $accent;
        margin-bottom: 1;
    }
    InfoScreen #info-content {
        height: auto;
        max-height: 20;
        border: none;
        background: $surface;
        padding: 0;
    }
    InfoScreen #close-btn {
        margin-top: 1;
        width: 100%;
    }
    """

    def __init__(self, title: str, content: str, **kwargs) -> None:
        super().__init__(**kwargs)
        self._title = title
        self._content = content

    def compose(self) -> ComposeResult:
        with Vertical(id="dialog"):
            yield Static(self._title, id="info-title")
            # TextArea 只读模式，内容可选中复制
            ta = _TextArea(self._content, id="info-content")
            ta.read_only = True
            yield ta
            yield Button("关闭", id="close-btn")

    def on_button_pressed(self, event: Button.Pressed) -> None:
        self.app.pop_screen()

    def on_key(self, event) -> None:
        if event.key == "escape":
            self.app.pop_screen()
