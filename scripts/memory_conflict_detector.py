#!/usr/bin/env python3
"""
ADDS Memory Conflict Detector — 记忆冲突检测器

设计目标：
- 检测 System Prompt 与固定记忆的冲突
- 轻量级冲突扫描（P0: 关键词互斥对，零 LLM 成本）
- 自动解决策略（Recency Bias）
- 冲突记录追踪

参考：P0-3 路线图 — 记忆冲突检测与解决
"""

import logging
import re
from dataclasses import dataclass, field
from datetime import datetime
from typing import Dict, List, Optional, Tuple

logger = logging.getLogger(__name__)


# ═══════════════════════════════════════════════════════════
# 轻量级冲突扫描器（P0）
# ═══════════════════════════════════════════════════════════

class LightweightConflictScanner:
    """P0: 关键词级冲突扫描（零 LLM 成本）

    在新记忆写入 index.mem 时执行，检测新老记忆的互斥关键词对。
    精度有限但零成本，发现可疑冲突后标记待审。
    """

    # 互斥关键词对（可扩展）
    CONFLICT_PAIRS = [
        ("JWT", "Session"),           # 认证方式冲突
        ("SQL", "NoSQL"),             # 数据库类型冲突
        ("REST", "GraphQL"),          # API 风格冲突
        ("Python", "Rust"),           # 语言冲突
        ("monolith", "microservice"), # 架构冲突
        ("sync", "async"),            # 并发模型冲突
        ("httpx", "requests"),        # HTTP 库冲突
        ("FastAPI", "Flask"),         # Web 框架冲突
        ("PostgreSQL", "MongoDB"),    # 数据库冲突
        ("Docker", "Podman"),         # 容器冲突
    ]

    def scan(self, new_memory: str, existing_memories: List[str]) -> List[Dict]:
        """扫描新记忆与现有记忆的冲突

        Args:
            new_memory: 新记忆内容
            existing_memories: 现有记忆内容列表

        Returns:
            冲突列表 [{"new_memory", "existing_memory", "conflict_type", "severity"}]
        """
        conflicts = []
        for kw_a, kw_b in self.CONFLICT_PAIRS:
            # 正向检查
            if kw_a.lower() in new_memory.lower():
                for existing in existing_memories:
                    if kw_b.lower() in existing.lower():
                        # 排除测试结果（如 "0 failed"）
                        conflicts.append({
                            "new_memory": new_memory,
                            "existing_memory": existing,
                            "conflict_type": f"{kw_a} vs {kw_b}",
                            "severity": "suspected",
                        })

            # 反向检查
            if kw_b.lower() in new_memory.lower():
                for existing in existing_memories:
                    if kw_a.lower() in existing.lower():
                        conflicts.append({
                            "new_memory": new_memory,
                            "existing_memory": existing,
                            "conflict_type": f"{kw_b} vs {kw_a}",
                            "severity": "suspected",
                        })

        return conflicts


# ═══════════════════════════════════════════════════════════
# 冲突检测与解决
# ═══════════════════════════════════════════════════════════

@dataclass
class ConflictRecord:
    """冲突记录"""
    description: str = ""
    source_a: str = ""     # "system_prompt" | "user_latest" | "fixed_memory"
    source_b: str = ""
    content_a: str = ""
    content_b: str = ""
    resolution: str = ""   # "system_prompt_wins" | "user_latest_wins" | "ask_user" | "pending"
    detected_at: str = ""
    conflict_type: str = ""


class MemoryConflictDetector:
    """记忆冲突检测器

    三层冲突检测：
    1. P0 轻量级关键词扫描（零 LLM 成本）
    2. 自动解决（Recency Bias 策略）
    3. 无法自动解决 → 标记待审
    """

    def __init__(self):
        self.scanner = LightweightConflictScanner()
        self.conflict_log: List[ConflictRecord] = []

    def check_new_memory(self, new_memory: str,
                         existing_memories: List[str]) -> List[Dict]:
        """P0: 检查新记忆与现有记忆的冲突

        Args:
            new_memory: 新记忆内容
            existing_memories: 现有固定记忆内容列表

        Returns:
            发现的冲突列表
        """
        conflicts = self.scanner.scan(new_memory, existing_memories)

        # 记录冲突
        for c in conflicts:
            record = ConflictRecord(
                description=c["conflict_type"],
                source_a="fixed_memory",
                source_b="new_memory",
                content_a=c["existing_memory"][:100],
                content_b=c["new_memory"][:100],
                resolution="pending",
                detected_at=datetime.now().isoformat(),
                conflict_type=c["conflict_type"],
            )
            self.conflict_log.append(record)
            logger.info(f"Conflict detected: {c['conflict_type']}")

        return conflicts

    def auto_resolve(self, conflict: ConflictRecord) -> Optional[str]:
        """自动解决冲突（Recency Bias 策略）

        自动解决规则：
        - System Prompt vs 固定记忆 → 自动以 System Prompt 为准
        - 用户最新指令 vs 固定记忆 → 自动以用户最新为准
        - System Prompt vs 用户最新指令 → ⚠️ 必须暂停确认

        Args:
            conflict: 冲突记录

        Returns:
            None 表示无法自动解决（需用户确认），否则返回解决方式
        """
        source_a = conflict.source_a
        source_b = conflict.source_b

        # System Prompt vs 固定记忆 → 自动以 System Prompt 为准
        if ("system_prompt" in (source_a, source_b) and
                "fixed_memory" in (source_a, source_b)):
            return "system_prompt_wins"

        # 用户最新指令 vs 固定记忆 → Recency Bias，以用户最新为准
        if ("user_latest" in (source_a, source_b) and
                "fixed_memory" in (source_a, source_b)):
            return "user_latest_wins"

        # System Prompt vs 用户最新指令 → 无法自动解决
        return None

    def resolve_conflict(self, conflict: ConflictRecord,
                         user_decision: str = "") -> str:
        """根据用户决策解决冲突

        Args:
            conflict: 冲突记录
            user_decision: 用户决策 (delete_memory / update_memory / keep_both)

        Returns:
            最终解决方式
        """
        # 先尝试自动解决
        auto = self.auto_resolve(conflict)
        if auto:
            conflict.resolution = auto
            return auto

        # 需要用户决策
        if user_decision:
            conflict.resolution = user_decision
            return user_decision

        conflict.resolution = "pending"
        return "pending"

    def get_pending_conflicts(self) -> List[ConflictRecord]:
        """获取待解决的冲突"""
        return [c for c in self.conflict_log if c.resolution == "pending"]

    def get_conflict_log(self) -> List[ConflictRecord]:
        """获取所有冲突记录"""
        return self.conflict_log

    def format_conflict_for_display(self, conflict: ConflictRecord) -> str:
        """格式化冲突信息用于显示"""
        lines = [
            f"⚠️ 冲突: {conflict.description}",
            f"   来源A ({conflict.source_a}): {conflict.content_a}",
            f"   来源B ({conflict.source_b}): {conflict.content_b}",
        ]
        if conflict.resolution != "pending":
            lines.append(f"   解决: {conflict.resolution}")
        else:
            lines.append("   状态: 待确认")
        return "\n".join(lines)
