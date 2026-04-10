#!/usr/bin/env python3
"""
ADDS Index Priority Sorter — index.mem 优先级排序器

设计目标：
- 计算记忆条目的优先级分数（6 个权重因子）
- 排序并分割为当前 index 和溢出区
- 支持代码热度地图（注意力热点）

参考：P0-3 路线图 — 优先级排序算法
"""

import logging
import math
import subprocess
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Tuple

logger = logging.getLogger(__name__)


# ═══════════════════════════════════════════════════════════
# 重要性权重常量
# ═══════════════════════════════════════════════════════════

CATEGORY_WEIGHTS = {
    "environment": 1.0,    # 环境事实不会过时
    "experience": 0.9,     # 经验教训长期有效
    "skill": 0.7,          # 技能可能过时
    "preference": 1.0,     # 用户偏好核心约束
}

# 时间衰减 lambda（约 14 天半衰期）
TIME_DECAY_LAMBDA = 0.05


@dataclass
class MemoryItem:
    """记忆条目（用于排序）"""
    id: str = ""
    content: str = ""
    category: str = "experience"     # environment | experience | skill | preference
    role: str = "common"             # common | dev | architect | qa | pm | reviewer
    module: str = ""                 # 相关模块
    tags: List[str] = field(default_factory=list)
    last_accessed: Optional[datetime] = None
    reference_count: int = 0
    system_prompt_related: bool = False
    invalidation_count: int = 0      # 被证伪次数
    rollback_count: int = 0          # 导致回滚次数
    status: str = "active"           # active | suspected | invalidated | demoted
    promoted: bool = False           # 是否已晋升
    promoted_at: str = ""            # 晋升时的 tag

    @property
    def importance_weight(self) -> float:
        return CATEGORY_WEIGHTS.get(self.category, 0.5)


class IndexPrioritySorter:
    """index.mem 内容的优先级排序器

    权重因子:
    1. 时间衰减: exp(-0.05 * days_since_last_access)
    2. 重要性权重: environment=1.0, experience=0.9, skill=0.7, preference=1.0
    3. 引用频率: (1 + log(reference_count + 1))
    4. System Prompt 关联度: +0.5
    5. 负反馈惩罚: 0.5^invalidation_count * 0.7^rollback_count
    6. 代码热度 (code_heat): 最近频繁修改的模块相关记忆临时加温
    """

    def __init__(self, project_root: str = "."):
        self.project_root = Path(project_root)

    def calculate_priority(self, item: MemoryItem,
                           code_heat_map: Optional[Dict[str, float]] = None) -> float:
        """计算记忆条目的优先级分数

        Args:
            item: 记忆条目
            code_heat_map: 代码热度地图 {"module": change_count}

        Returns:
            优先级分数（越高越重要）
        """
        # 已降级的条目优先级为 0
        if item.status == "demoted":
            return 0.0

        base_priority = item.importance_weight

        # 1. 时间衰减
        if item.last_accessed:
            days_since = (datetime.now() - item.last_accessed).days
            time_decay = math.exp(-TIME_DECAY_LAMBDA * max(0, days_since))
        else:
            time_decay = 0.5  # 无时间信息，中等衰减

        # 2. 引用频率
        ref_bonus = 1 + math.log(item.reference_count + 1)

        # 3. System Prompt 关联度
        sp_related = 0.5 if item.system_prompt_related else 0

        # 4. 负反馈惩罚
        negative_penalty = 0.5 ** item.invalidation_count
        rollback_penalty = 0.7 ** item.rollback_count

        # 5. 代码热度
        code_heat_bonus = 1.0
        if code_heat_map and item.module:
            heat = code_heat_map.get(item.module, 0)
            if heat > 0:
                code_heat_bonus = 1.0 + min(heat * 0.1, 0.5)  # 最多 +50%

        # 6. 晋升加成
        promote_bonus = 1.0
        if item.promoted:
            promote_bonus = 1.5

        return (base_priority * time_decay * ref_bonus
                * negative_penalty * rollback_penalty * code_heat_bonus * promote_bonus
                + sp_related)

    def sort_for_index(self, items: List[MemoryItem],
                       capacity: int = 2000,
                       code_heat_map: Optional[Dict[str, float]] = None
                       ) -> Tuple[List[MemoryItem], List[MemoryItem]]:
        """排序并分割为当前 index 和溢出区

        Args:
            items: 所有记忆条目
            capacity: index.mem 固定记忆区字符上限
            code_heat_map: 代码热度地图

        Returns:
            (current_index_items, overflow_items)
        """
        # 计算优先级并排序
        scored = [(item, self.calculate_priority(item, code_heat_map)) for item in items]
        scored.sort(key=lambda x: x[1], reverse=True)

        current = []
        overflow = []
        total_chars = 0

        for item, score in scored:
            item_chars = len(item.content) + 20  # 额外 20 字符用于元数据
            if total_chars + item_chars <= capacity:
                current.append(item)
                total_chars += item_chars
            else:
                overflow.append(item)

        # 自动降级检测
        for item in overflow:
            score = self.calculate_priority(item, code_heat_map)
            if score < 0.1:
                item.status = "demoted"
                logger.info(f"Auto-demoted: {item.id} (priority={score:.3f})")
            elif item.invalidation_count >= 3:
                item.status = "demoted"
                logger.info(f"Force-demoted (invalidation>=3): {item.id}")
            elif item.rollback_count >= 5:
                item.status = "demoted"
                logger.info(f"Force-demoted (rollback>=5): {item.id}")

        return current, overflow

    def build_code_heat_map(self, days: int = 7) -> Dict[str, float]:
        """构建代码热度地图

        通过 git log 统计最近 N 天的文件变更频率。

        Args:
            days: 统计天数

        Returns:
            {"module": change_count}
        """
        try:
            result = subprocess.run(
                ["git", "log", f"--since={days} days ago",
                 "--name-only", "--pretty=format:"],
                capture_output=True, text=True,
                cwd=str(self.project_root),
            )
            heat_map: Dict[str, float] = {}
            for line in result.stdout.strip().split("\n"):
                line = line.strip()
                if not line:
                    continue
                # 提取模块前缀
                parts = line.replace("\\", "/").split("/")
                # 跳过根目录文件和隐藏目录
                if len(parts) > 1 and not parts[0].startswith("."):
                    module = parts[1] if parts[0] in ("src", "scripts", "lib") else parts[0]
                    heat_map[module] = heat_map.get(module, 0) + 1
                elif len(parts) > 1:
                    module = parts[0]
                    heat_map[module] = heat_map.get(module, 0) + 1

            return heat_map
        except Exception as e:
            logger.debug(f"Failed to build code heat map: {e}")
            return {}

    def get_forced_reminders(self, items: List[MemoryItem],
                             role: str = "") -> List[MemoryItem]:
        """获取需要强制复读的记忆

        条件: invalidation_count >= 2 且未被 promote 到 SP

        Args:
            items: 所有固定记忆条目
            role: 当前 Agent 角色

        Returns:
            需要强制复读的条目列表
        """
        reminders = []
        for item in items:
            if item.invalidation_count >= 2 and not item.promoted:
                # 角色匹配
                item_role = item.role or "common"
                if item_role in ("common", role):
                    reminders.append(item)
        return reminders


# ═══════════════════════════════════════════════════════════
# index.mem 解析工具
# ═══════════════════════════════════════════════════════════

def parse_index_mem(content: str) -> List[MemoryItem]:
    """解析 index.mem 固定记忆区为 MemoryItem 列表

    支持的格式:
    - 简单行: "- 内容 | module: xxx | role: dev | tags: a, b | id: exp-001"
    - 带状态: "- ~~内容~~ ❌ | status: invalidated | id: exp-004"
    - 环境块: "### 项目环境" 下的 "- key: value" 行
    """
    import re

    items = []
    current_section = ""
    item_counter = 0

    for line in content.split("\n"):
        line = line.strip()

        # 检测章节
        if line.startswith("### "):
            current_section = line[4:].strip()
            continue

        # 解析列表项
        if not line.startswith("- "):
            continue

        item_counter += 1
        raw = line[2:]  # 去掉 "- "

        # 先按 | 分割，再处理每个部分
        parts = [p.strip() for p in raw.split("|")]
        content_text = parts[0] if parts else raw

        # 检测 invalidated 状态（删除线格式）
        status = "active"
        if content_text.startswith("~~") and "❌" in content_text:
            status = "invalidated"
            # 提取删除线外的内容
            strike_match = re.match(r'~~(.+?)~~\s*❌', content_text)
            if strike_match:
                content_text = strike_match.group(1).strip()

        # 提取元数据
        meta = {}
        for part in parts[1:]:
            if ":" in part:
                key, value = part.split(":", 1)
                key = key.strip()
                value = value.strip()
                if key == "tags":
                    meta["tags"] = [t.strip() for t in value.split(",")]
                elif key == "id":
                    meta["id"] = value
                elif key == "module":
                    meta["module"] = value
                elif key == "role":
                    meta["role"] = value
                elif key == "status":
                    meta["status"] = value
                elif key == "invalidation_count":
                    meta["invalidation_count"] = int(value)
                elif key == "promoted":
                    meta["promoted"] = value.lower() == "true"
                elif key == "promoted_at":
                    meta["promoted_at"] = value

        # 推断 category
        category = "experience"
        if current_section in ("项目环境",):
            category = "environment"
        elif current_section in ("已掌握技能",):
            category = "skill"
        elif current_section in ("用户偏好",):
            category = "preference"

        item = MemoryItem(
            id=meta.get("id", f"auto-{item_counter:03d}"),
            content=content_text,
            category=category,
            role=meta.get("role", "common"),
            module=meta.get("module", ""),
            tags=meta.get("tags", []),
            invalidation_count=meta.get("invalidation_count", 0),
            status=meta.get("status", status),
            promoted=meta.get("promoted", False),
            promoted_at=meta.get("promoted_at", ""),
        )

        items.append(item)

    return items


def build_index_content(items: List[MemoryItem],
                        index_entries: Optional[List[Dict]] = None,
                        conflict_records: Optional[List[Dict]] = None) -> str:
    """从 MemoryItem 列表重建 index.mem 内容

    Args:
        items: 固定记忆条目
        index_entries: 记忆索引表行
        conflict_records: 冲突记录

    Returns:
        index.mem 文件内容
    """
    # 按类别分组
    environments = []
    experiences = []
    skills = []
    preferences = []

    for item in items:
        if item.category == "environment":
            environments.append(item)
        elif item.category == "experience":
            experiences.append(item)
        elif item.category == "skill":
            skills.append(item)
        elif item.category == "preference":
            preferences.append(item)

    lines = []

    # 项目环境
    if environments:
        lines.append("### 项目环境")
        for item in environments:
            lines.append(_format_item(item))
        lines.append("")

    # 核心经验
    if experiences:
        lines.append("### 核心经验")
        for item in experiences:
            lines.append(_format_item(item))
        lines.append("")

    # 已掌握技能
    if skills:
        lines.append("### 已掌握技能")
        for item in skills:
            lines.append(_format_item(item))
        lines.append("")

    # 用户偏好
    if preferences:
        lines.append("### 用户偏好")
        for item in preferences:
            lines.append(_format_item(item))
        lines.append("")

    # 记忆索引
    if index_entries:
        lines.append("---")
        lines.append("")
        lines.append("## 记忆索引（线索，按需回溯）")
        lines.append("")
        lines.append("| 时间 | 文件 | 摘要 | 优先级 |")
        lines.append("|------|------|------|--------|")
        for entry in index_entries:
            time = entry.get("time", "")
            file = entry.get("file", "")
            summary = entry.get("summary", "")
            priority = entry.get("priority", "")
            lines.append(f"| {time} | {file} | {summary} | {priority} |")
        lines.append("")

    # 冲突记录
    if conflict_records:
        lines.append("---")
        lines.append("")
        lines.append("## 冲突记录")
        lines.append("")
        lines.append("| 检测时间 | 冲突描述 | 来源A | 来源B | 解决方式 |")
        lines.append("|----------|----------|-------|-------|----------|")
        for rec in conflict_records:
            time = rec.get("time", "")
            desc = rec.get("description", "")
            src_a = rec.get("source_a", "")
            src_b = rec.get("source_b", "")
            resolution = rec.get("resolution", "")
            lines.append(f"| {time} | {desc} | {src_a} | {src_b} | {resolution} |")
        lines.append("")

    return "\n".join(lines)


def _format_item(item: MemoryItem) -> str:
    """格式化单条记忆条目"""
    content = item.content
    if item.status == "invalidated":
        content = f"~~{content}~~ ❌"

    parts = [content]
    if item.module:
        parts.append(f"module: {item.module}")
    if item.role and item.role != "common":
        parts.append(f"role: {item.role}")
    if item.tags:
        parts.append(f"tags: {', '.join(item.tags)}")
    if item.status == "invalidated":
        parts.append(f"status: invalidated")
        if item.invalidation_count:
            parts.append(f"invalidation_count: {item.invalidation_count}")
    if item.promoted:
        parts.append(f"promoted: true")
        if item.promoted_at:
            parts.append(f"promoted_at: {item.promoted_at}")
    if item.id:
        parts.append(f"id: {item.id}")

    return "- " + " | ".join(parts)
