"""
皮肤适配器 — 将现有 SkinConfig 映射到 Textual CSS 变量
"""

from __future__ import annotations
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    pass


# Textual CSS 变量名 → SkinConfig 颜色键
_COLOR_MAP = {
    "$primary":    "banner_accent",
    "$accent":     "ui_accent",
    "$text":       "banner_text",
    "$dim":        "banner_dim",
    "$error":      "ui_error",
    "$success":    "ui_ok",
    "$warning":    "ui_warn",
    "$border":     "banner_border",
    "$label":      "ui_label",
    "$response":   "response_border",
}


def build_css_vars(skin) -> str:
    """从 SkinConfig 生成 Textual CSS 变量字符串"""
    lines = []
    for css_var, skin_key in _COLOR_MAP.items():
        color = skin.color(skin_key)
        if color:
            # Textual CSS 变量语法：直接在 :root 中定义
            lines.append(f"    {css_var}: {color};")
    return "\n".join(lines)


def get_color(skin, key: str, fallback: str = "#FFFFFF") -> str:
    """安全获取皮肤颜色，带 fallback"""
    if skin is None:
        return fallback
    return skin.color(key) or fallback


# 角色对应的颜色标识（用于标签页着色）
ROLE_COLORS = {
    "pm":         "#4dd0e1",   # 青色
    "architect":  "#FFD700",   # 金色
    "developer":  "#4caf50",   # 绿色
    "reviewer":   "#ffa726",   # 橙色
    "tester":     "#ce93d8",   # 紫色
}

ROLE_ICONS = {
    "pm":         "📋",
    "architect":  "🏗️",
    "developer":  "💻",
    "reviewer":   "🔍",
    "tester":     "🧪",
}


def role_color(role: str) -> str:
    return ROLE_COLORS.get(role, "#FFFFFF")


def role_icon(role: str) -> str:
    return ROLE_ICONS.get(role, "🤖")
