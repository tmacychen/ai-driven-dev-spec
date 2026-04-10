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
    import pyfiglet
except ImportError:
    pyfiglet = None

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
    "logo_font": "standard",
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
    def logo_font(self) -> str:
        """Logo 字体（pyfiglet 字体名）"""
        return self._config.get("logo_font", "standard")

    @property
    def logo_text(self) -> str:
        """Logo 文字（默认为 agent_name）"""
        return self._config.get("logo_text", "") or self.branding("agent_name", "ADDS")

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

ADDS_LOGO = [
    "    ___  ____  ____  ____ ",
    "   / _ |/ ___|/ ___||  _ \\",
    "  | | | | |   | |   | |_) |",
    "  | |_| | |___| |___|  _ < ",
    "   \\__|_|\\____|\\____|_| \\_\\",
]

# Logo 每行的颜色配置：(行号, 颜色, 是否加粗)
ADDS_LOGO_COLORS = [
    (0, "#FFD700", True),
    (1, "#FFD700", False),
    (2, "#FFBF00", True),
    (3, "#FFBF00", False),
    (4, "#FFD700", True),
]

ADDS_HERO = """
[dim #555555]┌──────────────────────────────────────────────────────────┐[/]
[dim #555555]│[/]  [bold #FFD700]⚡[/]  [dim #444444]═══════════════════════════════════════════  [bold #FFD700]⚡[/]  [dim #555555]│[/]
[dim #555555]│[/]  [bold #FFBF00]A D D S[/]  [dim #B8860B]·[/]  [dim #FFF8DC]A I - D r i v e n   A g e n t[/]             [dim #555555]│[/]
[dim #555555]│[/]  [bold #FFD700]⚡[/]  [dim #444444]═══════════════════════════════════════════  [bold #FFD700]⚡[/]  [dim #555555]│[/]
[dim #555555]└──────────────────────────────────────────────────────────┘[/]"""


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

def _render_builtin_logo(console: Console, title_color: str, accent_color: str, dim_color: str) -> None:
    """渲染内置 ADDS_LOGO（用皮肤颜色上色）"""
    logo_text = Text()
    for i, line in enumerate(ADDS_LOGO):
        style = f"bold {title_color}" if i % 2 == 0 else accent_color
        logo_text.append(line + "\n", style=style)
    subtitle = "A I - D r i v e n   D e v   S p e c"
    logo_text.append(subtitle, style=f"dim {dim_color}")
    console.print(Align.center(logo_text))


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

    logo = skin.banner_logo
    logo_font = skin.logo_font
    logo_text_str = skin.logo_text
    hero = skin.banner_hero
    agent_name = skin.branding("agent_name", "ADDS")

    console.print()

    # 渲染 Logo
    title_color = c["title"]
    accent_color = c["accent"]
    dim_color = c["dim"]

    if isinstance(logo, str) and logo.strip():
        # 方案 A：YAML 中的自定义 Rich markup 文本 — 直接渲染
        for line in logo.strip().split("\n"):
            console.print(Align.center(line))
    elif logo_font and pyfiglet:
        # 方案 B：pyfiglet 动态生成（推荐，无转义问题）
        try:
            fig_text = pyfiglet.figlet_format(logo_text_str, font=logo_font)
            logo_text = Text()
            for i, line in enumerate(fig_text.split("\n")):
                if not line.strip():
                    continue
                # 交替使用 title/accent 颜色
                style = f"bold {title_color}" if i % 2 == 0 else accent_color
                logo_text.append(line + "\n", style=style)
            subtitle = "A I - D r i v e n   D e v   S p e c"
            logo_text.append(subtitle, style=f"dim {dim_color}")
            console.print(Align.center(logo_text))
        except Exception:
            # 字体不存在时回退
            _render_builtin_logo(console, title_color, accent_color, dim_color)
    else:
        # 方案 C：内置 ADDS_LOGO
        _render_builtin_logo(console, title_color, accent_color, dim_color)

    console.print()

    # 左右分栏布局
    layout = Table.grid(padding=(0, 2))
    layout.add_column("left", justify="center")
    layout.add_column("right", justify="left")

    # 左侧：Hero + 模型信息
    left_lines = [""]
    if isinstance(hero, str) and hero.strip():
        # 自定义 hero（YAML 中的 Rich markup）
        for line in hero.strip().split("\n"):
            left_lines.append(line)
    else:
        # 默认 Hero：简洁文字风格（在 grid 中能正确渲染）
        left_lines.append(f"[bold {c['title']}]{agent_name}[/]  [{c['dim']}]·[/]  [{c['text']}]A I - D r i v e n   A g e n t[/]")
        left_lines.append(f"[dim {c['dim']}]──────────────────────────────────[/]")
    left_lines.append("")
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
