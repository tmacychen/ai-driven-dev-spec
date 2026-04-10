#!/usr/bin/env python3
"""
ADDS Role Memory Injector — 角色感知记忆注入器

设计目标：
- 根据 Agent 角色过滤固定记忆
- P0: role 字段 + 过滤注入（共享 index.mem）
- P1: 物理拆分到 index-{role}.mem

参考：P0-3 路线图 — 角色化记忆体系
"""

import logging
from dataclasses import dataclass
from typing import Dict, List, Optional

from index_priority_sorter import MemoryItem, parse_index_mem, build_index_content

logger = logging.getLogger(__name__)


@dataclass
class RoleMemoryConfig:
    """角色记忆配置"""
    # 各角色应注入的记忆类别
    role_categories: Dict[str, List[str]] = None

    def __post_init__(self):
        if self.role_categories is None:
            self.role_categories = {
                "pm": ["environment", "experience", "preference"],
                "architect": ["environment", "experience", "preference"],
                "developer": ["environment", "experience", "skill", "preference"],
                "tester": ["environment", "experience", "skill", "preference"],
                "reviewer": ["environment", "experience", "preference"],
            }


class RoleAwareMemoryInjector:
    """角色感知记忆注入器

    P0 策略: `role:` 字段 + 过滤注入
    - role: common → 所有角色都注入
    - role: {specific} → 仅注入给匹配角色
    - 未标记 role → 默认 common（向后兼容）

    角色与记忆维度对应:
    - Dev Agent → 记住"手"的动作（实现细节、API 技巧）
    - Architect Agent → 记住"界"的定义（模块边界、架构约束）
    - QA Agent → 记住"眼"的焦点（高风险代码特征、回归点）
    """

    def __init__(self, config: Optional[RoleMemoryConfig] = None):
        self.config = config or RoleMemoryConfig()

    def filter_memories_for_role(self, items: List[MemoryItem],
                                  current_role: str) -> List[MemoryItem]:
        """根据当前 Agent 角色过滤固定记忆

        规则:
        1. role: common → 所有角色都注入
        2. role: {specific} → 仅注入给匹配角色
        3. 未标记 role → 默认 common（向后兼容）
        4. 额外: 根据角色注入对应类别的记忆

        Args:
            items: 所有固定记忆条目
            current_role: 当前 Agent 角色

        Returns:
            过滤后的记忆条目列表
        """
        # 获取角色允许的类别
        allowed_categories = self.config.role_categories.get(
            current_role,
            ["environment", "experience", "preference"],
        )

        filtered = []
        for item in items:
            # 规则 1-3: role 字段过滤
            item_role = item.role or "common"
            if item_role == "common" or item_role == current_role:
                # 规则 4: 类别过滤
                if item.category in allowed_categories:
                    filtered.append(item)

        return filtered

    def build_memory_section(self, items: List[MemoryItem],
                             current_role: str,
                             forced_reminders: Optional[List[MemoryItem]] = None) -> str:
        """构建注入到 System Prompt 的记忆段落

        Args:
            items: 过滤后的记忆条目
            current_role: 当前 Agent 角色
            forced_reminders: 强制复读的记忆条目

        Returns:
            格式化的记忆段落文本
        """
        lines = []

        # 强制复读区（如有）
        if forced_reminders:
            lines.append("### ⚠️ 强制复读 — 历史回归风险")
            for item in forced_reminders:
                inv_count = item.invalidation_count
                lines.append(
                    f"- ⚠️ {item.content} (被证伪 {inv_count} 次，务必注意)"
                )
            lines.append("")

        # 固定记忆
        filtered = self.filter_memories_for_role(items, current_role)

        # 按类别分组
        environments = [i for i in filtered if i.category == "environment"]
        experiences = [i for i in filtered if i.category == "experience"]
        skills = [i for i in filtered if i.category == "skill"]
        preferences = [i for i in filtered if i.category == "preference"]

        if environments:
            lines.append("### 项目环境")
            for item in environments:
                content = item.content
                if item.status == "invalidated":
                    content = f"~~{content}~~ ❌ (已证伪)"
                lines.append(f"- {content}")

        if experiences:
            lines.append("### 核心经验")
            for item in experiences:
                content = item.content
                if item.status == "invalidated":
                    content = f"~~{content}~~ ❌ (已证伪)"
                lines.append(f"- {content}")

        if skills:
            lines.append(f"### {current_role.title()} 技能")
            for item in skills:
                lines.append(f"- {item.content}")

        if preferences:
            lines.append("### 用户偏好")
            for item in preferences:
                lines.append(f"- {item.content}")

        if not lines:
            return ""

        return "## Agent 记忆（P0-3 链式记忆）\n\n" + "\n".join(lines)

    def get_role_description(self, role: str) -> str:
        """获取角色记忆维度描述"""
        descriptions = {
            "developer": "记住'手'的动作 — 实现细节、API 技巧、具体代码模式",
            "architect": "记住'界'的定义 — 模块边界、架构约束、技术选型禁忌",
            "tester": "记住'眼'的焦点 — 高风险代码特征、回归点、边界用例",
            "pm": "记住'序'的节奏 — 需求优先级、依赖关系、里程碑",
            "reviewer": "记住'尺'的标准 — 代码质量阈值、安全红线、性能基准",
        }
        return descriptions.get(role, "通用记忆")
