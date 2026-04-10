#!/usr/bin/env python3
"""
ADDS Consistency Guard — 一致性守护（回归警报 + 元诊断）

设计目标：
- 回归警报: 历史碰撞检测（相似度 > 85%）
- 元诊断: 诊断为什么旧记忆没拦截住旧问题
- 三位一体防御: 直觉 / 记忆 / 工具
- 强制复读机制

参考：P0-3 路线图 — 回归警报与元诊断
"""

import logging
from dataclasses import dataclass
from typing import Dict, List, Optional

from memory_retriever import MemoryRetriever, RegexMemoryRetriever, SearchResult

logger = logging.getLogger(__name__)


# ═══════════════════════════════════════════════════════════
# 数据结构
# ═══════════════════════════════════════════════════════════

@dataclass
class DefenseFailureDiagnosis:
    """防御失效诊断结果"""
    failed_layer: str = ""       # intuition | memory | tool | multiple
    diagnosis: str = ""          # 诊断说明
    prescription: str = ""       # 修复建议


@dataclass
class RegressionAlarm:
    """回归警报"""
    current_failure: Dict = None
    historical_case: Optional[SearchResult] = None
    similarity: float = 0.0
    diagnosis: Optional[DefenseFailureDiagnosis] = None


# ═══════════════════════════════════════════════════════════
# 一致性守护
# ═══════════════════════════════════════════════════════════

class ConsistencyGuard:
    """一致性守护 — 回归警报与元诊断

    当 QA 发现一个 Bug 时，系统强制执行全量记忆检索。
    相似度 > 85% → 触发"回归警报" → 启动"元修复任务"。

    三位一体防御:
    ① 直觉 (Intuition) — System Prompt + 角色准则
    ② 记忆 (Memory) — index.mem
    ③ 工具 (Tools) — 测试集 / Linter / 静态分析

    防御优先级: 直觉 > 记忆 > 工具
    修复优先级: 工具 > 记忆 > 直觉（越早拦截越好）
    """

    SIMILARITY_THRESHOLD = 0.85  # 碰撞检测阈值

    def __init__(self, retriever: Optional[MemoryRetriever] = None):
        self.retriever = retriever

    async def analyze_failure(
        self,
        current_failure: Dict,
        sessions_dir: str = ".ai/sessions",
    ) -> Optional[RegressionAlarm]:
        """分析失败是否为旧问题回归

        流程:
        1. 将当前错误日志 + 受影响代码片段作为查询
        2. 在所有历史 .mem 归档中检索相似案例
        3. 相似度 > 85% → 触发"回归警报"
        4. 回归警报 → 启动"元修复任务"

        Args:
            current_failure: {"error", "code_snippet", "module", ...}
            sessions_dir: sessions 目录路径

        Returns:
            RegressionAlarm 或 None
        """
        # 构建查询
        query = self._build_failure_query(current_failure)

        # 检索相似案例
        retriever = self.retriever or RegexMemoryRetriever(sessions_dir)
        similar_cases = await retriever.search(query, top_k=5)

        if not similar_cases:
            return None

        # 碰撞检测（P0: 基于关键词重叠度的简化相似度）
        for case in similar_cases:
            similarity = self._compute_similarity(current_failure, case)
            if similarity > self.SIMILARITY_THRESHOLD:
                # 元诊断
                diagnosis = self._diagnose_defense_failure(
                    current_failure, case
                )

                return RegressionAlarm(
                    current_failure=current_failure,
                    historical_case=case,
                    similarity=similarity,
                    diagnosis=diagnosis,
                )

        return None

    def _build_failure_query(self, failure: Dict) -> str:
        """构建失败检索查询"""
        parts = []
        error = failure.get("error", "")
        if error:
            parts.append(error)
        code = failure.get("code_snippet", "")
        if code:
            parts.append(code[:200])
        module = failure.get("module", "")
        if module:
            parts.append(module)
        return " ".join(parts)

    def _compute_similarity(self, failure: Dict,
                            case: SearchResult) -> float:
        """计算失败与历史案例的相似度

        P0 简化: 基于关键词重叠度
        """
        error = failure.get("error", "").lower()
        code = failure.get("code_snippet", "").lower()
        combined = f"{error} {code}"

        case_content = case.content.lower()

        # 提取关键词
        error_words = set(combined.split())
        case_words = set(case_content.split())

        # 去除常见词
        common = {"的", "了", "在", "是", "and", "the", "to", "for",
                  "in", "of", "a", "an", "is", "are", "was", "were",
                  "has", "have", "had", "not", "but", "or", "from"}

        error_words -= common
        case_words -= common

        if not error_words:
            return 0.0

        # Jaccard 相似度
        intersection = error_words & case_words
        union = error_words | case_words
        jaccard = len(intersection) / len(union) if union else 0

        # 如果错误类型完全匹配，加权
        if any(kw in case_content for kw in ["error", "exception", "traceback"]):
            if any(kw in combined for kw in ["error", "exception", "traceback"]):
                jaccard = min(1.0, jaccard + 0.2)

        # 如果模块匹配，加权
        module = failure.get("module", "").lower()
        if module and module in case_content:
            jaccard = min(1.0, jaccard + 0.15)

        return jaccard

    def _diagnose_defense_failure(
        self,
        current_failure: Dict,
        historical_case: SearchResult,
    ) -> DefenseFailureDiagnosis:
        """元诊断: 为什么旧记忆没有拦截住旧问题的回归？

        诊断三层防御的失效点:
        ① 直觉层失效 → 这条经验没进入 System Prompt
        ② 记忆层失效 → 描述太模糊/注意力不足/被其他信息淹没
        ③ 工具层失效 → 没有 lint/test 规则覆盖这类问题

        P0: 基于规则诊断（不调用 LLM）
        """
        # 判断是否在固定记忆中
        in_fixed_memory = historical_case.source == "固定记忆"

        # 判断记忆描述是否足够具体
        content = historical_case.content
        is_vague = len(content) < 30 or not any(
            kw in content for kw in ["必须", "禁止", "不要", "always", "never", "must"]
        )

        # 诊断
        if not in_fixed_memory:
            # 记忆层失效 — 经验只在 .mem 文件中，未被注入上下文
            return DefenseFailureDiagnosis(
                failed_layer="memory",
                diagnosis="该经验仅在历史 .mem 文件中，未被注入到当前上下文。"
                         "Agent 无法看到这条历史教训。",
                prescription=f"建议将此经验升级为固定记忆（写入 index.mem），"
                            f"或在 SP 顶部强制置顶。来源: {historical_case.file}",
            )

        if is_vague:
            # 记忆层失效 — 描述太模糊
            return DefenseFailureDiagnosis(
                failed_layer="memory",
                diagnosis="该经验已在固定记忆中，但描述不够具体/强制性不足。"
                         "Agent 可能忽略了模糊的建议。",
                prescription="重写记忆描述，增加强制性关键词"
                            "（如'必须'、'禁止'、'永远不要'），提升注意力权重。",
            )

        # 如果在固定记忆中且描述具体 → 可能是直觉层失效
        return DefenseFailureDiagnosis(
            failed_layer="intuition",
            diagnosis="该经验已在固定记忆中且描述具体，但 Agent 仍犯同样错误。"
                     "可能是 System Prompt 的约束力不足，或 Agent 注意力被其他信息淹没。",
            prescription="建议 promote 到 System Prompt 顶部，或在接下来 3 个任务中"
                        "强制复读此条经验。",
        )

    def format_alarm(self, alarm: RegressionAlarm) -> str:
        """格式化回归警报用于显示"""
        lines = [
            f"🚨 回归警报！相似度: {alarm.similarity:.0%}",
            f"",
            f"当前失败:",
            f"  错误: {alarm.current_failure.get('error', 'unknown')}",
            f"  模块: {alarm.current_failure.get('module', 'unknown')}",
            f"",
            f"历史案例:",
            f"  来源: {alarm.historical_case.file if alarm.historical_case else 'unknown'}",
            f"  内容: {alarm.historical_case.content[:100] if alarm.historical_case else 'unknown'}",
            f"",
        ]

        if alarm.diagnosis:
            lines.extend([
                f"元诊断:",
                f"  失效层: {alarm.diagnosis.failed_layer}",
                f"  诊断: {alarm.diagnosis.diagnosis}",
                f"  处方: {alarm.diagnosis.prescription}",
            ])

        return "\n".join(lines)
