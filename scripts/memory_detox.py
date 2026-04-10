#!/usr/bin/env python3
"""
ADDS Memory Detox — 记忆排毒引擎

设计目标：
- 验证性失效 (Failure-Driven Invalidation)
- 负反馈惩罚 (Negative Penalty)
- 轻量级冲突扫描 (Lightweight Conflict Scan)
- 失效标记与降级

参考：P0-3 路线图 — 记忆排毒与遗忘机制
"""

import logging
from dataclasses import dataclass, field
from datetime import datetime
from typing import Dict, List, Optional

from index_priority_sorter import IndexPrioritySorter, MemoryItem
from memory_conflict_detector import MemoryConflictDetector, ConflictRecord

logger = logging.getLogger(__name__)


# ═══════════════════════════════════════════════════════════
# 失效评估 Prompt
# ═══════════════════════════════════════════════════════════

INVALIDATION_PROMPT = """分析以下任务失败是否与引用的固定记忆直接相关:

任务失败摘要:
{failure_summary}

引用的固定记忆:
{referenced_memories}

对每条引用的固定记忆，判断:
- related: 失败是否与该记忆直接相关 (true/false)
- reason: 如果相关，解释该记忆如何导致了失败
- severity: low / medium / high（该记忆的错误程度）

格式:
- memory_id: ...
- related: ...
- reason: ...
- severity: ...
"""


@dataclass
class InvalidationResult:
    """失效评估结果"""
    memory_id: str = ""
    related: bool = False
    reason: str = ""
    severity: str = "low"     # low / medium / high
    old_invalidation_count: int = 0
    new_invalidation_count: int = 0
    demoted: bool = False     # 是否被降级
    demotion_reason: str = ""


class MemoryDetox:
    """记忆排毒引擎

    三大排毒手段:
    ① 验证性失效 — 任务失败且与某条固定记忆直接相关
    ② 负反馈惩罚 — Agent 引用固定记忆后导致任务回滚
    ③ 轻量级冲突扫描 — 新记忆写入时检测关键词互斥

    降级路径:
    index.mem (活跃) → index-prev.mem (降级) → 可回溯
    """

    def __init__(self, project_root: str = "."):
        self.project_root = project_root
        self.sorter = IndexPrioritySorter(project_root)
        self.conflict_detector = MemoryConflictDetector()

    async def evaluate_invalidation(
        self,
        session_mem: str,
        failed_task_context: Dict,
        referenced_memories: List[MemoryItem],
    ) -> List[InvalidationResult]:
        """验证性失效: 检测失败任务是否与某条固定记忆相关

        流程:
        1. 提取本次 session 中引用的固定记忆条目
        2. 检测失败是否与某条固定记忆直接相关
        3. 相关 → 标记 invalidated, 增加 invalidation_count
        4. 优先级 < 0.1 → 降级到 index-prev.mem

        Args:
            session_mem: Session .mem 内容
            failed_task_context: 失败上下文 {"error", "code_snippet", ...}
            referenced_memories: 本次引用的固定记忆条目

        Returns:
            失效评估结果列表
        """
        if not referenced_memories:
            return []

        results = []

        for mem_item in referenced_memories:
            # 简单规则检测（P0: 不调用 LLM，基于关键词匹配）
            is_related = self._detect_invalidation_by_rules(
                session_mem, failed_task_context, mem_item
            )

            result = InvalidationResult(
                memory_id=mem_item.id,
                related=is_related,
                old_invalidation_count=mem_item.invalidation_count,
            )

            if is_related:
                mem_item.invalidation_count += 1
                mem_item.status = "invalidated"
                result.new_invalidation_count = mem_item.invalidation_count
                result.reason = self._generate_invalidation_reason(
                    failed_task_context, mem_item
                )
                result.severity = self._assess_severity(failed_task_context)

                # 检查是否需要降级
                priority = self.sorter.calculate_priority(mem_item)
                if priority < 0.1:
                    mem_item.status = "demoted"
                    result.demoted = True
                    result.demotion_reason = "invalidation"
                    logger.info(
                        f"Demoted (invalidation): {mem_item.id}, "
                        f"priority={priority:.3f}, count={mem_item.invalidation_count}"
                    )
                elif mem_item.invalidation_count >= 3:
                    mem_item.status = "demoted"
                    result.demoted = True
                    result.demotion_reason = "force_invalidation_3"
                    logger.info(f"Force-demoted (invalidation>=3): {mem_item.id}")

            results.append(result)

        return results

    def apply_rollback_penalty(self, item: MemoryItem) -> bool:
        """负反馈惩罚: 回滚计数 +1，检查是否需要降级

        Args:
            item: 导致回滚的记忆条目

        Returns:
            是否被降级
        """
        item.rollback_count += 1

        priority = self.sorter.calculate_priority(item)
        if priority < 0.1:
            item.status = "demoted"
            logger.info(
                f"Demoted (rollback): {item.id}, "
                f"priority={priority:.3f}, count={item.rollback_count}"
            )
            return True

        if item.rollback_count >= 5:
            item.status = "demoted"
            logger.info(f"Force-demoted (rollback>=5): {item.id}")
            return True

        return False

    def check_new_memory_conflicts(self, new_memory: str,
                                    existing_memories: List[str]) -> List[Dict]:
        """轻量级冲突扫描

        Args:
            new_memory: 新记忆内容
            existing_memories: 现有固定记忆内容列表

        Returns:
            发现的冲突列表
        """
        return self.conflict_detector.check_new_memory(
            new_memory, existing_memories
        )

    def _detect_invalidation_by_rules(
        self,
        session_mem: str,
        failed_context: Dict,
        memory_item: MemoryItem,
    ) -> bool:
        """基于规则的失效检测（P0: 不调用 LLM）

        规则:
        1. 失败中包含该记忆的模块/标签关键词
        2. 记忆内容与错误信息有直接重叠
        3. 记忆的 category 是 skill（技能类更易过时）
        """
        error = failed_context.get("error", "").lower()
        code = failed_context.get("code_snippet", "").lower()
        combined = f"{error} {code}"

        # 规则 1: 模块/标签关键词匹配
        if memory_item.module and memory_item.module.lower() in combined:
            return True

        # 规则 2: 记忆内容关键词重叠
        content_words = set(memory_item.content.lower().split())
        error_words = set(combined.split())
        overlap = content_words & error_words
        # 至少 3 个词重叠才认为相关（排除常见词）
        common_words = {"的", "了", "在", "是", "and", "the", "to", "for", "in"}
        meaningful_overlap = overlap - common_words
        if len(meaningful_overlap) >= 3:
            return True

        # 规则 3: 技能类记忆 + 同模块失败 → 高度可疑
        if memory_item.category == "skill" and memory_item.module:
            if memory_item.module.lower() in combined:
                return True

        return False

    def _generate_invalidation_reason(self, failed_context: Dict,
                                       memory_item: MemoryItem) -> str:
        """生成失效原因描述"""
        error = failed_context.get("error", "unknown error")
        return (
            f"任务失败 ({error}) 与固定记忆 [{memory_item.id}] "
            f"模块={memory_item.module} 相关"
        )

    def _assess_severity(self, failed_context: Dict) -> str:
        """评估失败严重度"""
        error = failed_context.get("error", "").lower()
        if any(kw in error for kw in ["critical", "fatal", "segfault", "oom"]):
            return "high"
        if any(kw in error for kw in ["exception", "error", "failed", "traceback"]):
            return "medium"
        return "low"
