"""
ADDS CLI 皮肤引擎

基于 Rich 库的终端美化系统，支持 YAML 皮肤配置。
参考 ai-cli-skins 项目设计。
"""

import copy
import os
from pathlib import Path
from typing import Dict, Any, Optional, List

try:
    import yaml
except ImportError:
    yaml = None

try:
    from rich.console import Console
    from rich.panel import Panel
    from rich.table import Table
    from rich.align import Align
    from rich.text import Text
except ImportError:
    Console = None


# ═══════════════════════════════════════════════════════════════
# 默认皮肤配置
# ═══════════════════════════════════════════════════════════════

DEFAULT_SKIN = {
    "name": "default",
    "description": "ADDS 默认金色主题",
    "colors": {
        "banner_border": "#CD7F32",
        "banner_title": "#FFD700",
        "banner_accent": "#FFBF00",
        "banner_dim": "#B8860B",
        "banner_text": "#FFF8DC",
        "ui_accent": "#FFBF00",
        "ui_label": "#4dd0e1",
        "ui_ok": "#4caf50",
        "ui_error": "#ef5350",
        "ui_warn": "#ffa726",
        "prompt": "#FFF8DC",
        "input_rule": "#CD7F32",
        "response_border": "#FFD700",
        "session_label": "#DAA520",
        "session_border": "#8B8682",
    },
    "spinner": {
        "waiting_faces": ["(⚙)", "(◆)", "(◇)"],
        "thinking_faces": ["(⚙)", "(⌁)", "(<>)"],
        "thinking_verbs": ["processing", "analyzing", "computing"],
        "wings": [["⟪⚡", "⚡⟫"], ["⟪●", "●⟫"]],
    },
    "branding": {
        "agent_name": "ADDS",
        "welcome": "Welcome! Type your message or /help for commands.",
        "goodbye": "Goodbye!",
        "response_label": " ⚡ ADDS ",
        "prompt_symbol": "❯",
        "help_header": "(⚡) Available Commands",
    },
    "tool_prefix": "┊",
    "tool_emojis": {},
    "banner_logo": "",
    "banner_hero": "",
}


def _deep_merge(base: Dict, override: Dict) -> Dict:
    """Deep merge override into base dict."""
    result = copy.deepcopy(base)
    for key, value in override.items():
        if key in result and isinstance(result[key], dict) and isinstance(value, dict):
            result[key] = _deep_merge(result[key], value)
        else:
            result[key] = value
    return result


class SkinConfig:
    """皮肤配置"""

    def __init__(self, config: Dict[str, Any]):
        self._config = _deep_merge(DEFAULT_SKIN, config)
        self.name = self._config.get("name", "default")
        self.description = self._config.get("description", "")
        self._colors = self._config.get("colors", {})
        self._spinner = self._config.get("spinner", {})
        self._branding = self._config.get("branding", {})

    def color(self, key: str, default: str = "") -> str:
        """获取颜色值"""
        return self._colors.get(key, default or DEFAULT_SKIN["colors"].get(key, ""))

    def branding(self, key: str, default: str = "") -> str:
        """获取品牌文案"""
        return self._branding.get(key, default or DEFAULT_SKIN["branding"].get(key, ""))

    def spinner(self, key: str) -> List:
        """获取 spinner 配置"""
        return self._spinner.get(key, DEFAULT_SKIN["spinner"].get(key, []))

    def tool_emoji(self, tool_name: str) -> Optional[str]:
        """获取工具 emoji"""
        return self._config.get("tool_emojis", {}).get(tool_name)

    @property
    def banner_logo(self) -> str:
        return self._config.get("banner_logo", "")

    @property
    def banner_hero(self) -> str:
        return self._config.get("banner_hero", "")

    @property
    def tool_prefix(self) -> str:
        return self._config.get("tool_prefix", "┊")

    @property
    def prompt_symbol(self) -> str:
        return self.branding("prompt_symbol", "❯")


# ═══════════════════════════════════════════════════════════════
# ADDS Logo 和 Banner
# ═══════════════════════════════════════════════════════════════

ADDS_LOGO = r"""
[bold #FFD700]    █████╗ ███████╗ ██████╗ ███████╗██╗  ██╗[/]
[#FFD700]   ██╔══██╗██╔════╝██╔════╝ ██╔════╝╚██╗██╔╝[/]
[bold #FFBF00]   ███████║███████╗██║  ███╗█████╗  ╚███╔╝ [/]
[#FFBF00]   ██╔══██║╚════██║██║   ██║╚════╝  ██╔██╗ [/]
[bold #FFD700]   ██║  ██║███████║╚██████╔╝       ██╔╝ ██╗[/]
[#FFD700]   ╚═╝  ╚═╝╚══════╝ ╚═════╝        ╚═╝  ╚═╝[/]
[dim #B8860B]      A I - D r i v e n   D e v   S p e c[/]"""

ADDS_HERO = """
[dim #555555]⠁⠁⠁⠁⠁⠁⠁⠁⠁⠁⠁⠁⠁⠁⠁⠁⠁⠁⠁⠁⠁⠁⠁⠁⠁⠁⠁⠁[/]
[dim #666666]  [bold #AAAAAA]ADDS[/]  [dim #444444]═══════════════════════════════  [bold #AAAAAA]AGENT[/]  [dim #444444][/]
[dim #555555]⠁⠁⠁⠁⠁⠁⠁⠁⠁⠁⠁⠁⠁⠁⠁⠁⠁⠁⠁⠁⠁⠁⠁⠁⠁⠁⠁⠁[/]"""


def load_skin(skin_name: str, config_dir: Optional[str] = None) -> SkinConfig:
    """加载皮肤配置"""
    if yaml is None:
        return SkinConfig({"name": skin_name})

    if config_dir is None:
        config_dir = os.path.expanduser("~/.adds/skins/")

    skin_path = Path(config_dir) / f"{skin_name}.yaml"
    if not skin_path.exists():
        skin_path = Path(config_dir) / f"{skin_name}.yml"
    if not skin_path.exists():
        return SkinConfig({"name": skin_name})

    with open(skin_path, "r", encoding="utf-8") as f:
        data = yaml.safe_load(f) or {}

    return SkinConfig(data)


def list_skins(config_dir: Optional[str] = None) -> List[str]:
    """列出可用皮肤"""
    if config_dir is None:
        config_dir = os.path.expanduser("~/.adds/skins/")

    skins_path = Path(config_dir)
    if not skins_path.exists():
        return []

    return [p.stem for p in skins_path.glob("*.yaml")] + [p.stem for p in skins_path.glob("*.yml")]


# ═══════════════════════════════════════════════════════════════
# Banner 渲染
# ═══════════════════════════════════════════════════════════════

def render_banner(console: Console, skin: SkinConfig, model_name: str = "",
                  context_window: int = 0, role: str = "") -> None:
    """渲染 ADDS 启动 Banner"""
    c = {
        "accent": skin.color("banner_accent"),
        "dim": skin.color("banner_dim"),
        "text": skin.color("banner_text"),
        "label": skin.color("ui_label"),
        "title": skin.color("banner_title"),
        "border": skin.color("banner_border"),
        "session": skin.color("session_border"),
    }

    logo = skin.banner_logo or ADDS_LOGO
    hero = skin.banner_hero or ADDS_HERO
    agent_name = skin.branding("agent_name", "ADDS")

    console.print()
    console.print(Align.center(logo))
    console.print()

    # 左右分栏布局
    layout = Table.grid(padding=(0, 2))
    layout.add_column("left", justify="center")
    layout.add_column("right", justify="left")

    # 左侧：Hero + 模型信息
    left_lines = ["", hero, ""]
    if model_name:
        left_lines.append(
            f"[{c['accent']}]{model_name}[/] [{c['dim']}]·[/] "
            f"[{c['dim']}]{context_window:,} context[/]"
        )
    if role:
        left_lines.append(f"[dim {c['dim']}]Role: {role}[/]")
    left_content = "\n".join(left_lines)

    # 右侧：角色列表
    right_lines = [f"[bold {c['accent']}]Built-in Roles[/]"]
    roles = [
        ("pm", "项目经理"),
        ("architect", "架构师"),
        ("developer", "开发者"),
        ("tester", "测试工程师"),
        ("reviewer", "代码审查员"),
    ]
    for name, desc in roles:
        right_lines.append(f"[dim {c['dim']}]{name}:[/] [{c['text']}]{desc}[/]")
    right_lines.append("")
    right_lines.append(f"[dim {c['dim']}]adds start --role <name>[/]")
    right_content = "\n".join(right_lines)

    layout.add_row(Align.center(left_content), right_content)

    panel = Panel(
        layout,
        title=f"[bold {c['title']}]{agent_name} Agent[/]",
        border_style=c["border"],
        padding=(0, 2),
    )
    console.print(panel)

    welcome = skin.branding("welcome", "")
    if welcome:
        console.print()
        console.print(f"[{c['text']}]{welcome}[/]")

    console.print()


def render_prompt(console: Console, skin: SkinConfig) -> str:
    """渲染输入提示符"""
    symbol = skin.prompt_symbol
    prompt_color = skin.color("prompt")
    return f"[{prompt_color}]{symbol}[/]"


def render_thinking(console: Console, skin: SkinConfig, text: str) -> None:
    """渲染思考过程"""
    dim_color = skin.color("banner_dim")
    text_color = skin.color("banner_text")
    console.print(f"[dim {dim_color}]🧠 思考中...[/]")
    console.print(f"[dim {dim_color}]{text}[/]")
    console.print()


def render_response(console: Console, skin: SkinConfig, text: str) -> None:
    """渲染模型响应（带边框面板）"""
    border_color = skin.color("response_border")
    label = skin.branding("response_label", " ⚡ ADDS ")

    panel = Panel(
        text,
        title=f"[{border_color}]{label}[/]",
        border_style=border_color,
        padding=(0, 1),
    )
    console.print(panel)


def render_error(console: Console, skin: SkinConfig, text: str) -> None:
    """渲染错误信息"""
    error_color = skin.color("ui_error")
    console.print(f"[bold {error_color}]❌ {text}[/]")


def render_success(console: Console, skin: SkinConfig, text: str) -> None:
    """渲染成功信息"""
    ok_color = skin.color("ui_ok")
    console.print(f"[{ok_color}]✅ {text}[/]")


def render_status(console: Console, skin: SkinConfig, items: dict) -> None:
    """渲染状态信息列表"""
    label_color = skin.color("ui_label")
    text_color = skin.color("banner_text")
    dim_color = skin.color("banner_dim")

    for key, value in items.items():
        console.print(f"  [{label_color}]{key}:[/] [{text_color}]{value}[/]")


def create_console() -> Console:
    """创建 Rich Console 实例"""
    if Console is None:
        raise ImportError("rich 库未安装，请运行: pip install rich")
    return Console()
