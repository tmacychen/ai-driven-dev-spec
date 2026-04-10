#!/usr/bin/env python3
"""
ADDS Memory Manager — 记忆管理器（两层 + 进化 + 检索 + 冲突检测）

设计目标：
- 两层记忆: 索引层（常驻上下文）+ 记忆层（按需加载）
- 记忆进化: 高价值经验自动升级为固定记忆
- 角色化记忆: 按角色过滤注入
- 记忆排毒: 失效标记与降级
- 反思协议: 第一人称角色反思

参考：P0-3 路线图 — 记忆进化机制
"""

import logging
import re
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Tuple

from index_priority_sorter import (
    IndexPrioritySorter, MemoryItem,
    parse_index_mem, build_index_content,
)
from memory_conflict_detector import MemoryConflictDetector, ConflictRecord
from memory_retriever import MemoryRetriever, RegexMemoryRetriever, SearchResult
from memory_detox import MemoryDetox, InvalidationResult
from role_memory_injector import RoleAwareMemoryInjector
from consistency_guard import ConsistencyGuard, RegressionAlarm

logger = logging.getLogger(__name__)


# ═══════════════════════════════════════════════════════════
# 反思协议 Prompt
# ═══════════════════════════════════════════════════════════

REFLECTION_PROMPT = """[Framework Protocol: Role-Based Evolution]

当前任务已闭环。作为 **{role_name}**，请审阅本次任务的全部过程，并执行以下思考逻辑：

1. **提取核心事实**: 本次任务中，哪些信息是本角色未来**必须**知道的？
   - 不是"发生了什么"，而是"什么会改变我未来的决策"

2. **更新行为守则**: 基于此任务，我以后在执行 **{role_name}** 职责时，应该增加/修改哪条准则？
   - 格式: "以后遇到 {条件} 时，必须 {行为}"
   - 例: "以后调用 C 接口后，必须显式调用 Box::from_raw"

3. **压缩与抽象**: 请将上述内容压缩为高密度的 Markdown 条目，准备更新至你的 index.mem。
   - 不要记录琐碎的过程，只记录改变你未来决策的"精华"
   - 每条不超过 50 字

输出格式:
- fact: 核心事实（1-3 条）
- rule: 行为守则（0-2 条）
- memory_candidate: 压缩后的记忆条目（0-3 条）
- role: {role_name}
"""

# LLM 评估升级 Prompt
UPGRADE_EVALUATION_PROMPT = """评估以下 session 记忆内容中的经验价值。

Session 摘要:
{mem_summary}

四种升级类型和条件:
1. 环境事实 — 新的环境约束/配置
2. 经验教训 — 踩坑后获得的通用教训
3. 技能模式 — 成功完成某种模式 >= 2 次
4. 用户偏好 — 用户重复强调 >= 2 次

请输出每条值得升级的经验:
- category: environment | experience | skill | preference
- confidence: 0.0-1.0
- content: 压缩后的记忆内容（不超过 50 字）
- reasoning: 评估理由
- role: {role}
"""


# ═══════════════════════════════════════════════════════════
# 数据结构
# ═══════════════════════════════════════════════════════════

@dataclass
class MemoryUpgradeEvaluation:
    """记忆升级评估结果"""
    should_upgrade: bool = False
    category: str = "experience"   # environment | experience | skill | preference
    confidence: float = 0.0
    content: str = ""
    reasoning: str = ""
    role: str = "common"

    def needs_review(self) -> bool:
        """是否需要更强模型复核

        规则:
        - confidence < 0.7 → 需要复核
        - 涉及用户偏好 → 需要复核（不可替用户决策）
        """
        if self.confidence < 0.7:
            return True
        if self.category == "preference":
            return True
        return False


@dataclass
class MemoryStatus:
    """记忆系统状态概览"""
    total_fixed_memories: int = 0
    active_count: int = 0
    suspected_count: int = 0
    invalidated_count: int = 0
    demoted_count: int = 0
    capacity_used: int = 0
    capacity_total: int = 2000
    pending_conflicts: int = 0
    forced_reminders_count: int = 0


# ═══════════════════════════════════════════════════════════
# 记忆管理器
# ═══════════════════════════════════════════════════════════

class MemoryManager:
    """记忆管理器 — 两层记忆 + 进化 + 排毒 + 角色化

    核心职责:
    1. 读写 index.mem（固定记忆 + 索引）
    2. 记忆进化（升级/降级）
    3. 冲突检测
    4. 角色化注入
    5. 记忆检索
    6. 排毒机制
    """

    DEFAULT_INDEX_MEM = """# ADDS 记忆索引
# Page: 1
# 更新时间: {timestamp}
# 此文件始终注入上下文，是 Agent 的"长期记忆索引"
# Prev: null
# Next: null
# ⚠️ 固定记忆优先级低于 System Prompt，冲突以 System Prompt 为准

---

## 固定记忆（精华，始终可用）

### 项目环境
- 项目: 新项目 | id: env-001

### 核心经验
（暂无）

### 已掌握技能
（暂无）

### 用户偏好
（暂无）

---

## 记忆索引（线索，按需回溯）

| 时间 | 文件 | 摘要 | 优先级 |
|------|------|------|--------|

---

## 冲突记录

（暂无冲突记录）
"""

    def __init__(self, sessions_dir: str = ".ai/sessions",
                 project_root: str = ".",
                 max_fixed_memory_chars: int = 2000):
        self.sessions_dir = Path(sessions_dir)
        self.sessions_dir.mkdir(parents=True, exist_ok=True)
        self.project_root = project_root
        self.max_fixed_memory_chars = max_fixed_memory_chars

        # 子模块
        self.sorter = IndexPrioritySorter(project_root)
        self.conflict_detector = MemoryConflictDetector()
        self.retriever = RegexMemoryRetriever(str(self.sessions_dir))
        self.injector = RoleAwareMemoryInjector()
        self.detox = MemoryDetox(project_root)
        self.guard = ConsistencyGuard(self.retriever)

        # index.mem 路径
        self.index_mem_path = self.sessions_dir / "index.mem"

    # ════════════════════════════════════════════
    # index.mem 读写
    # ════════════════════════════════════════════

    def ensure_index_mem(self) -> None:
        """确保 index.mem 存在"""
        if not self.index_mem_path.exists():
            content = self.DEFAULT_INDEX_MEM.format(
                timestamp=datetime.now().strftime("%Y-%m-%d %H:%M")
            )
            self.index_mem_path.write_text(content, encoding="utf-8")
            logger.info("Created default index.mem")

    def read_index_mem(self) -> Tuple[str, List[MemoryItem]]:
        """读取 index.mem

        Returns:
            (raw_content, parsed_items)
        """
        self.ensure_index_mem()
        content = self.index_mem_path.read_text(encoding="utf-8")

        # 提取固定记忆区
        fixed_section = self._extract_fixed_section(content)
        items = parse_index_mem(fixed_section)

        return content, items

    def write_index_mem(self, items: List[MemoryItem],
                        index_entries: Optional[List[Dict]] = None,
                        conflict_records: Optional[List[Dict]] = None) -> None:
        """写入 index.mem

        Args:
            items: 固定记忆条目
            index_entries: 记忆索引表行
            conflict_records: 冲突记录
        """
        # 构建头部
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M")

        # 读取现有的链式指针信息
        prev_val = "null"
        next_val = "null"
        if self.index_mem_path.exists():
            existing = self.index_mem_path.read_text(encoding="utf-8")
            prev_match = re.search(r'# Prev:\s*(\S+)', existing)
            next_match = re.search(r'# Next:\s*(\S+)', existing)
            if prev_match:
                prev_val = prev_match.group(1)
            if next_match:
                next_val = next_match.group(1)

        header = f"""# ADDS 记忆索引
# Page: 1
# 更新时间: {timestamp}
# 此文件始终注入上下文，是 Agent 的"长期记忆索引"
# Prev: {prev_val}
# Next: {next_val}
# ⚠️ 固定记忆优先级低于 System Prompt，冲突以 System Prompt 为准

---

"""

        # 构建固定记忆内容
        fixed_content = build_index_content(items, index_entries, conflict_records)

        # 写入
        self.index_mem_path.write_text(header + fixed_content, encoding="utf-8")
        logger.info(f"Updated index.mem ({len(items)} items)")

    def _extract_fixed_section(self, content: str) -> str:
        """提取 index.mem 的固定记忆区"""
        # 找到 "---" 后的内容
        parts = content.split("---", 1)
        if len(parts) > 1:
            return parts[1]
        return content

    # ════════════════════════════════════════════
    # 记忆进化
    # ════════════════════════════════════════════

    async def evaluate_and_upgrade(
        self,
        mem_content: str,
        role: str = "common",
        min_confidence: float = 0.6,
    ) -> List[MemoryUpgradeEvaluation]:
        """评估 .mem 内容中的经验价值

        使用反思协议（第一人称角色反思）替代旁观评估。

        Args:
            mem_content: .mem 文件内容
            role: 产生此评估的角色

        Returns:
            升级评估结果列表
        """
        # P0: 基于规则评估（不调用 LLM）
        evaluations = self._rule_based_evaluate(mem_content, role)

        # 过滤低置信度
        evaluations = [e for e in evaluations if e.confidence >= min_confidence]

        # 执行升级
        for ev in evaluations:
            if ev.should_upgrade:
                await self._upgrade_memory(ev)

        return evaluations

    def _rule_based_evaluate(self, mem_content: str,
                              role: str) -> List[MemoryUpgradeEvaluation]:
        """基于规则的记忆评估（P0: 不调用 LLM）

        规则:
        1. 包含"决定"、"选择"、"结论"等决策词 → experience
        2. 包含"必须"、"禁止"、"不要"等强制词 → experience（高置信度）
        3. 包含技术栈/框架名 → environment
        4. 包含"以后"、"下次"、"注意"等 → experience
        5. 包含"用户要求"、"用户偏好" → preference
        """
        evaluations = []
        content_lower = mem_content.lower()

        # 提取关键段落（摘要区的非空行）
        summary_lines = []
        for line in mem_content.split("\n"):
            line = line.strip()
            if not line or line.startswith("#") or line.startswith("---"):
                continue
            if line.startswith("### [") or line.startswith("## "):
                continue
            summary_lines.append(line)

        for line in summary_lines:
            # 决策类
            if any(kw in line for kw in ["决定", "选择", "结论", "方案", "采用"]):
                evaluations.append(MemoryUpgradeEvaluation(
                    should_upgrade=True,
                    category="experience",
                    confidence=0.75,
                    content=line[:50],
                    reasoning="包含决策/选择关键词",
                    role=role,
                ))

            # 强制类
            if any(kw in line for kw in ["必须", "禁止", "不要", "不能", "避免", "永远不"]):
                evaluations.append(MemoryUpgradeEvaluation(
                    should_upgrade=True,
                    category="experience",
                    confidence=0.85,
                    content=line[:50],
                    reasoning="包含强制约束关键词",
                    role=role,
                ))

            # 环境类
            if any(kw in line for kw in ["框架", "版本", "依赖", "配置", "安装", "Python", "Rust", "FastAPI"]):
                evaluations.append(MemoryUpgradeEvaluation(
                    should_upgrade=True,
                    category="environment",
                    confidence=0.8,
                    content=line[:50],
                    reasoning="包含环境/配置信息",
                    role="common",
                ))

            # 偏好类
            if any(kw in line for kw in ["用户要求", "用户偏好", "喜欢", "希望"]):
                evaluations.append(MemoryUpgradeEvaluation(
                    should_upgrade=True,
                    category="preference",
                    confidence=0.7,
                    content=line[:50],
                    reasoning="包含用户偏好信息",
                    role="common",
                ))

        # 去重
        seen = set()
        unique = []
        for ev in evaluations:
            if ev.content not in seen:
                seen.add(ev.content)
                unique.append(ev)

        return unique

    async def _upgrade_memory(self, evaluation: MemoryUpgradeEvaluation) -> bool:
        """将评估结果升级为固定记忆

        流程:
        1. 轻量级冲突扫描
        2. 无冲突 → 写入 index.mem
        3. 有冲突 → 标记待审
        """
        _, existing_items = self.read_index_mem()
        existing_contents = [item.content for item in existing_items]

        # 冲突扫描
        conflicts = self.detox.check_new_memory_conflicts(
            evaluation.content, existing_contents
        )

        if conflicts:
            logger.warning(
                f"Conflict detected for upgrade: {conflicts[0]['conflict_type']}"
            )
            return False

        # 写入
        new_item = MemoryItem(
            id=f"exp-{len(existing_items)+1:03d}",
            content=evaluation.content,
            category=evaluation.category,
            role=evaluation.role,
            status="active",
        )
        existing_items.append(new_item)

        # 容量检查 + 优先级排序
        code_heat_map = self.sorter.build_code_heat_map()
        current, overflow = self.sorter.sort_for_index(
            existing_items, self.max_fixed_memory_chars, code_heat_map
        )

        self.write_index_mem(current)

        if overflow:
            logger.info(f"Overflow: {len(overflow)} items demoted")
            self._write_prev_index(overflow)

        return True

    def _write_prev_index(self, overflow_items: List[MemoryItem]) -> None:
        """将溢出条目写入 index-prev.mem"""
        prev_path = self.sessions_dir / "index-prev.mem"

        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M")

        header = f"""# ADDS 记忆索引
# Page: 2
# 更新时间: {timestamp}
# 此文件是降级记忆区，按需回溯
# Prev: null
# Next: index.mem
# ⚠️ 降级记忆优先级较低，不自动注入上下文

---

"""
        content = build_index_content(overflow_items)
        prev_path.write_text(header + content, encoding="utf-8")

    # ════════════════════════════════════════════
    # 记忆注入
    # ════════════════════════════════════════════

    def build_memory_injection(self, role: str = "") -> str:
        """构建注入到 System Prompt 的记忆段落

        Args:
            role: 当前 Agent 角色

        Returns:
            格式化的记忆段落文本
        """
        _, items = self.read_index_mem()

        # 获取强制复读
        forced_reminders = self.sorter.get_forced_reminders(items, role)

        # 角色过滤
        return self.injector.build_memory_section(items, role, forced_reminders)

    # ════════════════════════════════════════════
    # 记忆检索
    # ════════════════════════════════════════════

    async def search_memory(self, query: str, top_k: int = 5) -> List[SearchResult]:
        """搜索记忆"""
        return await self.retriever.search(query, top_k)

    # ════════════════════════════════════════════
    # 排毒与回归检测
    # ════════════════════════════════════════════

    async def check_regression(self, failure: Dict) -> Optional[RegressionAlarm]:
        """检查失败是否为旧问题回归"""
        return await self.guard.analyze_failure(
            failure, str(self.sessions_dir)
        )

    async def evaluate_invalidation(
        self, session_mem: str, failed_context: Dict,
        referenced_memory_ids: Optional[List[str]] = None,
    ) -> List[InvalidationResult]:
        """验证性失效检测"""
        _, items = self.read_index_mem()

        # 筛选引用的记忆
        if referenced_memory_ids:
            referenced = [i for i in items if i.id in referenced_memory_ids]
        else:
            referenced = items  # 无指定则检查全部

        results = await self.detox.evaluate_invalidation(
            session_mem, failed_context, referenced
        )

        # 更新 index.mem
        if any(r.related for r in results):
            self.write_index_mem(items)

        return results

    # ════════════════════════════════════════════
    # 状态与查询
    # ════════════════════════════════════════════

    def get_status(self) -> MemoryStatus:
        """获取记忆系统状态概览"""
        _, items = self.read_index_mem()

        # 计算容量
        content_str = "\n".join(item.content for item in items)

        return MemoryStatus(
            total_fixed_memories=len(items),
            active_count=sum(1 for i in items if i.status == "active"),
            suspected_count=sum(1 for i in items if i.status == "suspected"),
            invalidated_count=sum(1 for i in items if i.status == "invalidated"),
            demoted_count=sum(1 for i in items if i.status == "demoted"),
            capacity_used=len(content_str),
            capacity_total=self.max_fixed_memory_chars,
            pending_conflicts=len(self.conflict_detector.get_pending_conflicts()),
            forced_reminders_count=len(self.sorter.get_forced_reminders(items)),
        )

    def get_item_by_id(self, item_id: str) -> Optional[MemoryItem]:
        """按 ID 查找记忆条目"""
        _, items = self.read_index_mem()
        for item in items:
            if item.id == item_id:
                return item
        return None

    def update_item(self, item_id: str, updates: Dict) -> bool:
        """更新记忆条目

        Args:
            item_id: 条目 ID
            updates: 更新字段 {"content", "status", "role", ...}

        Returns:
            是否更新成功
        """
        _, items = self.read_index_mem()

        for item in items:
            if item.id == item_id:
                for key, value in updates.items():
                    if hasattr(item, key):
                        setattr(item, key, value)
                self.write_index_mem(items)
                return True

        return False

    def delete_item(self, item_id: str) -> bool:
        """删除记忆条目（从 index.mem 移除）"""
        _, items = self.read_index_mem()
        new_items = [i for i in items if i.id != item_id]

        if len(new_items) == len(items):
            return False

        self.write_index_mem(new_items)
        return True

    def add_index_entry(self, time: str, file: str,
                        summary: str, priority: str = "中") -> None:
        """添加记忆索引条目"""
        content, items = self.read_index_mem()

        # 解析现有索引表
        index_entries = self._parse_index_entries(content)
        index_entries.append({
            "time": time,
            "file": file,
            "summary": summary,
            "priority": priority,
        })

        # 解析冲突记录
        conflict_records = self._parse_conflict_records(content)

        self.write_index_mem(items, index_entries, conflict_records)

    def add_conflict_record(self, description: str, source_a: str,
                            source_b: str, resolution: str) -> None:
        """添加冲突记录"""
        content, items = self.read_index_mem()

        index_entries = self._parse_index_entries(content)
        conflict_records = self._parse_conflict_records(content)
        conflict_records.append({
            "time": datetime.now().strftime("%m-%d %H:%M"),
            "description": description,
            "source_a": source_a,
            "source_b": source_b,
            "resolution": resolution,
        })

        self.write_index_mem(items, index_entries, conflict_records)

    def checkpoint(self, tag: str) -> str:
        """记忆快照（checkpoint）

        复制 index.mem → index-{tag}.mem

        Args:
            tag: 快照标签（如 "v1.0.0"）

        Returns:
            快照文件路径
        """
        self.ensure_index_mem()
        content = self.index_mem_path.read_text(encoding="utf-8")

        checkpoint_path = self.sessions_dir / f"index-{tag}.mem"
        checkpoint_path.write_text(content, encoding="utf-8")

        logger.info(f"Memory checkpoint: {checkpoint_path}")
        return str(checkpoint_path)

    # ════════════════════════════════════════════
    # 解析辅助
    # ════════════════════════════════════════════

    def _parse_index_entries(self, content: str) -> List[Dict]:
        """解析 index.mem 中的记忆索引表"""
        entries = []
        in_table = False
        for line in content.split("\n"):
            if "| 时间 |" in line or "|------|" in line:
                in_table = True
                continue
            if in_table and line.startswith("|") and line.strip() != "":
                parts = [p.strip() for p in line.split("|")]
                # 过滤空元素
                parts = [p for p in parts if p]
                if len(parts) >= 4 and parts[0] != "时间":
                    entries.append({
                        "time": parts[0],
                        "file": parts[1],
                        "summary": parts[2],
                        "priority": parts[3] if len(parts) > 3 else "中",
                    })
            elif in_table and not line.startswith("|"):
                in_table = False
        return entries

    def _parse_conflict_records(self, content: str) -> List[Dict]:
        """解析 index.mem 中的冲突记录"""
        records = []
        in_table = False
        for line in content.split("\n"):
            if "| 检测时间 |" in line or "|----------|" in line:
                in_table = True
                continue
            if in_table and line.startswith("|") and line.strip() != "":
                parts = [p.strip() for p in line.split("|")]
                parts = [p for p in parts if p]
                if len(parts) >= 5 and parts[0] != "检测时间":
                    records.append({
                        "time": parts[0],
                        "description": parts[1],
                        "source_a": parts[2],
                        "source_b": parts[3],
                        "resolution": parts[4] if len(parts) > 4 else "",
                    })
            elif in_table and not line.startswith("|"):
                in_table = False
        return records
