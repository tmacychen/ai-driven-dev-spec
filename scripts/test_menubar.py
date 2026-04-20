#!/usr/bin/env python3
"""
tui-menubar 功能测试脚本

测试策略：不启动 TUI，只测试纯 Python 逻辑：
  - 数据模型（MenuEntry、MENU_DEFINITIONS、SKIN_NAMES）
  - 皮肤持久化（load_skin_setting / save_skin_setting）
  - AgentStatusScreen 数据渲染逻辑
  - app.py 中各 action 方法的存在性与签名

运行方式：
  python3 scripts/test_menubar.py
"""

from __future__ import annotations

import json
import os
import sys
import tempfile
import traceback
from pathlib import Path

# 确保 scripts/ 在 sys.path
SCRIPTS_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(SCRIPTS_DIR))

PASS = "✅"
FAIL = "❌"
results: list[tuple[str, bool, str]] = []


def test(name: str):
    """测试装饰器"""
    def decorator(fn):
        try:
            fn()
            results.append((name, True, ""))
        except Exception as e:
            results.append((name, False, f"{type(e).__name__}: {e}\n{traceback.format_exc()}"))
        return fn
    return decorator


# ---------------------------------------------------------------------------
# 1. 导入测试
# ---------------------------------------------------------------------------

@test("1.1 menubar 模块可正常导入")
def _():
    from tui.widgets.menubar import (
        MenuEntry, MENU_DEFINITIONS, SKIN_NAMES,
        load_skin_setting, save_skin_setting,
        MenuBar, MenuBarItem,
        DropdownSeparator, DropdownItem, DropdownMenu, DropdownOverlay,
        AgentStatusScreen,
    )


@test("1.2 app 模块可正常导入")
def _():
    from tui.app import ADDSApp


# ---------------------------------------------------------------------------
# 2. 数据模型测试
# ---------------------------------------------------------------------------

@test("2.1 MenuEntry dataclass 字段完整")
def _():
    from tui.widgets.menubar import MenuEntry
    e = MenuEntry(label="Test", action="test_action", payload="p", separator=False, submenu="")
    assert e.label == "Test"
    assert e.action == "test_action"
    assert e.payload == "p"
    assert e.separator is False
    assert e.submenu == ""


@test("2.2 MenuEntry separator 默认值")
def _():
    from tui.widgets.menubar import MenuEntry
    sep = MenuEntry(separator=True)
    assert sep.separator is True
    assert sep.label == ""
    assert sep.action == ""


@test("2.3 MENU_DEFINITIONS 包含 agent/view/app 三组")
def _():
    from tui.widgets.menubar import MENU_DEFINITIONS
    assert set(MENU_DEFINITIONS.keys()) == {"agent", "view", "app"}


@test("2.4 agent 菜单包含所有必需条目")
def _():
    from tui.widgets.menubar import MENU_DEFINITIONS
    entries = MENU_DEFINITIONS["agent"]
    labels = [e.label for e in entries if not e.separator]
    assert "New Agent..." in labels
    assert "Close Agent" in labels
    assert "List Roles" in labels
    assert "Agent Status" in labels


@test("2.5 view 菜单包含所有必需条目")
def _():
    from tui.widgets.menubar import MENU_DEFINITIONS
    entries = MENU_DEFINITIONS["view"]
    labels = [e.label for e in entries if not e.separator]
    assert "Toggle Split View" in labels
    assert "Toggle Permission Sidebar" in labels
    assert "Switch Skin ▶" in labels
    assert "Help" in labels


@test("2.6 app 菜单包含 About ADDS 和 Quit")
def _():
    from tui.widgets.menubar import MENU_DEFINITIONS
    entries = MENU_DEFINITIONS["app"]
    labels = [e.label for e in entries if not e.separator]
    assert "About ADDS" in labels
    assert "Quit" in labels


@test("2.7 SKIN_NAMES 包含 7 个皮肤")
def _():
    from tui.widgets.menubar import SKIN_NAMES
    assert len(SKIN_NAMES) == 7
    skin_ids = [s[1] for s in SKIN_NAMES]
    for expected in ["default", "cyberpunk", "matrix", "nordic", "sakura", "skynet", "vault-tec"]:
        assert expected in skin_ids, f"缺少皮肤: {expected}"


@test("2.8 Switch Skin ▶ 的 action 为 open_skin_submenu")
def _():
    from tui.widgets.menubar import MENU_DEFINITIONS
    skin_entry = next(e for e in MENU_DEFINITIONS["view"] if e.label == "Switch Skin ▶")
    assert skin_entry.action == "open_skin_submenu"
    assert skin_entry.submenu == "skin"


@test("2.9 agent 菜单有且仅有 1 条分隔线")
def _():
    from tui.widgets.menubar import MENU_DEFINITIONS
    seps = [e for e in MENU_DEFINITIONS["agent"] if e.separator]
    assert len(seps) == 1


@test("2.10 view 菜单有 2 条分隔线")
def _():
    from tui.widgets.menubar import MENU_DEFINITIONS
    seps = [e for e in MENU_DEFINITIONS["view"] if e.separator]
    assert len(seps) == 2


# ---------------------------------------------------------------------------
# 3. 皮肤持久化测试
# ---------------------------------------------------------------------------

@test("3.1 load_skin_setting 文件不存在时返回 default")
def _():
    from tui.widgets.menubar import load_skin_setting
    result = load_skin_setting("/nonexistent/path/settings.json")
    assert result == "default", f"期望 'default'，得到 '{result}'"


@test("3.2 load_skin_setting 读取正确的皮肤名称")
def _():
    from tui.widgets.menubar import load_skin_setting
    with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
        json.dump({"ui": {"skin": "cyberpunk"}, "other": "data"}, f)
        tmp_path = f.name
    try:
        result = load_skin_setting(tmp_path)
        assert result == "cyberpunk", f"期望 'cyberpunk'，得到 '{result}'"
    finally:
        os.unlink(tmp_path)


@test("3.3 load_skin_setting JSON 格式错误时返回 default")
def _():
    from tui.widgets.menubar import load_skin_setting
    with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
        f.write("{ invalid json }")
        tmp_path = f.name
    try:
        result = load_skin_setting(tmp_path)
        assert result == "default"
    finally:
        os.unlink(tmp_path)


@test("3.4 load_skin_setting ui.skin 字段缺失时返回 default")
def _():
    from tui.widgets.menubar import load_skin_setting
    with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
        json.dump({"other": "data"}, f)
        tmp_path = f.name
    try:
        result = load_skin_setting(tmp_path)
        assert result == "default"
    finally:
        os.unlink(tmp_path)


@test("3.5 save_skin_setting 写入新文件")
def _():
    from tui.widgets.menubar import save_skin_setting, load_skin_setting
    with tempfile.TemporaryDirectory() as tmpdir:
        path = os.path.join(tmpdir, "settings.json")
        save_skin_setting("matrix", path)
        result = load_skin_setting(path)
        assert result == "matrix", f"期望 'matrix'，得到 '{result}'"


@test("3.6 save_skin_setting 保留其他字段（merge 不覆盖）")
def _():
    from tui.widgets.menubar import save_skin_setting
    with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
        json.dump({"model": "gpt-4", "ui": {"theme": "dark"}}, f)
        tmp_path = f.name
    try:
        save_skin_setting("nordic", tmp_path)
        with open(tmp_path) as f:
            data = json.load(f)
        assert data["model"] == "gpt-4", "其他字段被覆盖了"
        assert data["ui"]["skin"] == "nordic"
        assert data["ui"]["theme"] == "dark", "ui 内其他字段被覆盖了"
    finally:
        os.unlink(tmp_path)


@test("3.7 皮肤持久化 round-trip（属性 2）")
def _():
    from tui.widgets.menubar import save_skin_setting, load_skin_setting, SKIN_NAMES
    with tempfile.TemporaryDirectory() as tmpdir:
        path = os.path.join(tmpdir, "settings.json")
        for _, skin_id in SKIN_NAMES:
            save_skin_setting(skin_id, path)
            result = load_skin_setting(path)
            assert result == skin_id, f"round-trip 失败: 写入 '{skin_id}'，读回 '{result}'"


@test("3.8 皮肤名称映射完整性（属性 3）")
def _():
    from tui.widgets.menubar import SKIN_NAMES
    skins_dir = SCRIPTS_DIR / "skins"
    for display_name, skin_id in SKIN_NAMES:
        yaml_file = skins_dir / f"adds_{skin_id}.yaml"
        assert yaml_file.exists(), f"皮肤文件不存在: {yaml_file}"


# ---------------------------------------------------------------------------
# 4. WorkspaceState 与 AgentStatusScreen 数据测试
# ---------------------------------------------------------------------------

@test("4.1 WorkspaceState 包含 AgentStatusScreen 所需字段")
def _():
    from tui.state import WorkspaceState, WorkspaceStatus
    ws = WorkspaceState(
        workspace_id="pm-001",
        agent_role="pm",
        token_used=1024,
        token_budget=128000,
        status=WorkspaceStatus.ACTIVE,
    )
    assert ws.workspace_id == "pm-001"
    assert ws.agent_role == "pm"
    assert ws.token_used == 1024
    assert ws.token_budget == 128000
    assert ws.status.value == "active"


@test("4.2 AgentStatusScreen 数据内容完整性（属性 4）")
def _():
    """验证 AgentStatusScreen 渲染所需的数据字段均可访问"""
    from tui.state import WorkspaceState, WorkspaceStatus
    ws = WorkspaceState(
        workspace_id="dev-002",
        agent_role="developer",
        token_used=5000,
        token_budget=128000,
        status=WorkspaceStatus.ACTIVE,
    )
    # 模拟 AgentStatusScreen.compose 中的数据访问
    token_info = f"{ws.token_used} / {ws.token_budget}"
    status_info = ws.status.value if hasattr(ws.status, "value") else str(ws.status)
    assert "dev-002" in ws.workspace_id
    assert "developer" in ws.agent_role
    assert "5000" in token_info
    assert "128000" in token_info
    assert status_info == "active"


# ---------------------------------------------------------------------------
# 5. ADDSApp action 方法存在性测试
# ---------------------------------------------------------------------------

@test("5.1 ADDSApp 包含 action_switch_skin 方法")
def _():
    from tui.app import ADDSApp
    assert hasattr(ADDSApp, "action_switch_skin"), "缺少 action_switch_skin"
    import inspect
    sig = inspect.signature(ADDSApp.action_switch_skin)
    assert "skin_name" in sig.parameters, "action_switch_skin 缺少 skin_name 参数"


@test("5.2 ADDSApp 包含 action_list_roles 方法")
def _():
    from tui.app import ADDSApp
    assert hasattr(ADDSApp, "action_list_roles")


@test("5.3 ADDSApp 包含 action_agent_status 方法")
def _():
    from tui.app import ADDSApp
    assert hasattr(ADDSApp, "action_agent_status")


@test("5.4 ADDSApp 包含 action_about 方法")
def _():
    from tui.app import ADDSApp
    assert hasattr(ADDSApp, "action_about")


@test("5.5 ADDSApp 包含 action_toggle_split 方法")
def _():
    from tui.app import ADDSApp
    assert hasattr(ADDSApp, "action_toggle_split")


@test("5.6 ADDSApp 包含 action_focus_menubar 方法")
def _():
    from tui.app import ADDSApp
    assert hasattr(ADDSApp, "action_focus_menubar")


@test("5.7 ADDSApp BINDINGS 包含 alt 绑定")
def _():
    from tui.app import ADDSApp
    binding_keys = [b.key for b in ADDSApp.BINDINGS]
    assert "alt" in binding_keys, f"BINDINGS 中缺少 alt，当前: {binding_keys}"


@test("5.8 ADDSApp compose 方法包含 MenuBar")
def _():
    import inspect
    from tui.app import ADDSApp
    source = inspect.getsource(ADDSApp.compose)
    assert "MenuBar" in source, "compose 方法中未找到 MenuBar"


@test("5.9 ADDSApp on_mount 包含 load_skin_setting 调用")
def _():
    import inspect
    from tui.app import ADDSApp
    source = inspect.getsource(ADDSApp.on_mount)
    assert "load_skin_setting" in source, "on_mount 中未找到 load_skin_setting"


@test("5.10 ADDSApp 包含 on_menu_bar_open_dropdown 消息处理器")
def _():
    from tui.app import ADDSApp
    assert hasattr(ADDSApp, "on_menu_bar_open_dropdown"), "缺少 on_menu_bar_open_dropdown"


# ---------------------------------------------------------------------------
# 6. MenuBar 类结构测试
# ---------------------------------------------------------------------------

@test("6.1 MenuBar 包含 3 个菜单项定义")
def _():
    from tui.widgets.menubar import MenuBar
    assert len(MenuBar.MENU_ITEMS) == 3
    menu_ids = [mid for _, mid in MenuBar.MENU_ITEMS]
    assert "agent" in menu_ids
    assert "view" in menu_ids
    assert "app" in menu_ids


@test("6.2 MenuBar 包含 action_activate_menu 方法")
def _():
    from tui.widgets.menubar import MenuBar
    assert hasattr(MenuBar, "action_activate_menu")


@test("6.3 MenuBar 包含 deactivate 方法")
def _():
    from tui.widgets.menubar import MenuBar
    assert hasattr(MenuBar, "deactivate")


@test("6.4 MenuBar 包含 on_key 方法")
def _():
    from tui.widgets.menubar import MenuBar
    assert hasattr(MenuBar, "on_key")


@test("6.5 MenuBar BINDINGS 包含 alt 绑定")
def _():
    from tui.widgets.menubar import MenuBar
    binding_keys = [b.key for b in MenuBar.BINDINGS]
    assert "alt" in binding_keys, f"MenuBar BINDINGS 缺少 alt，当前: {binding_keys}"


@test("6.6 MenuBar 包含 OpenDropdown 消息类")
def _():
    from tui.widgets.menubar import MenuBar
    assert hasattr(MenuBar, "OpenDropdown")
    assert hasattr(MenuBar, "ItemClicked")


# ---------------------------------------------------------------------------
# 7. DropdownOverlay 结构测试
# ---------------------------------------------------------------------------

@test("7.1 DropdownOverlay 继承自 ModalScreen")
def _():
    from textual.screen import ModalScreen
    from tui.widgets.menubar import DropdownOverlay
    assert issubclass(DropdownOverlay, ModalScreen)


@test("7.2 DropdownOverlay 使用 MENU_DEFINITIONS 作为默认 entries")
def _():
    import inspect
    from tui.widgets.menubar import DropdownOverlay, MENU_DEFINITIONS
    source = inspect.getsource(DropdownOverlay.__init__)
    assert "MENU_DEFINITIONS" in source


@test("7.3 DropdownOverlay 支持自定义 entries（皮肤子菜单）")
def _():
    import inspect
    from tui.widgets.menubar import DropdownOverlay
    sig = inspect.signature(DropdownOverlay.__init__)
    assert "entries" in sig.parameters


@test("7.4 DropdownItem.on_click 不使用 call_action（回归）")
def _():
    import inspect, re
    from tui.widgets.menubar import DropdownItem
    source = inspect.getsource(DropdownItem.on_click)
    # 确保没有实际调用 self.app.call_action(...)，注释里出现没问题
    actual_calls = re.findall(r'self\.app\.call_action\s*\(', source)
    assert len(actual_calls) == 0, f"on_click 中仍在调用不存在的 call_action: {actual_calls}"
    assert "action_" in source, "on_click 应通过 action_ 方法名调用"


# ---------------------------------------------------------------------------
# 8. 分屏切换 round-trip 测试（属性 5）
# ---------------------------------------------------------------------------

@test("8.1 WorkspaceState split_enabled 默认为 False")
def _():
    from tui.state import WorkspaceState
    ws = WorkspaceState(workspace_id="test-001", agent_role="pm")
    assert ws.split_enabled is False


@test("8.2 split_enabled 可以切换（round-trip）")
def _():
    from tui.state import WorkspaceState
    ws = WorkspaceState(workspace_id="test-001", agent_role="pm")
    initial = ws.split_enabled
    ws.split_enabled = not ws.split_enabled
    ws.split_enabled = not ws.split_enabled
    assert ws.split_enabled == initial, "两次切换后状态应与初始相同"


# ---------------------------------------------------------------------------
# 结果汇总
# ---------------------------------------------------------------------------

def main():
    print("\n" + "=" * 60)
    print("  tui-menubar 测试报告")
    print("=" * 60)

    passed = sum(1 for _, ok, _ in results if ok)
    failed = sum(1 for _, ok, _ in results if not ok)

    for name, ok, err in results:
        icon = PASS if ok else FAIL
        print(f"  {icon}  {name}")
        if not ok and err:
            # 只打印第一行错误信息
            first_line = err.strip().split("\n")[0]
            print(f"       → {first_line}")

    print("=" * 60)
    print(f"  总计: {len(results)} 个测试  |  通过: {passed}  |  失败: {failed}")
    print("=" * 60 + "\n")

    if failed > 0:
        print("失败详情：")
        for name, ok, err in results:
            if not ok:
                print(f"\n{'─'*50}")
                print(f"  {FAIL} {name}")
                print(err)
        sys.exit(1)
    else:
        print("所有测试通过！\n")
        sys.exit(0)


if __name__ == "__main__":
    main()
