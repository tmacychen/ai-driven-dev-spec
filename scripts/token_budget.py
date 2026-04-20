#!/usr/bin/env python3
"""
ADDS Token Budget Manager — Token 预算管理器

设计目标：
- 管理上下文窗口的 Token 预算分配
- 提供 Layer1/Layer2 压缩触发判断
- 监控各区域 Token 使用量

参考：P0-2 上下文压缩策略 — Token 预算管理
"""

import json
import logging
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, Optional

logger = logging.getLogger(__name__)


# ═══════════════════════════════════════════════════════════
# 预算分配比例（参考 P0-2 路线图）
# ═══════════════════════════════════════════════════════════

SYSTEM_PROMPT_RATIO = 0.15    # 15% — 系统提示词
MEMORY_RATIO = 0.10           # 10% — 固定记忆 + 上一个摘要
HISTORY_RATIO = 0.55          # 55% — 当前 session 对话
TOOL_RESULT_RATIO = 0.15      # 15% — 工具输出
RESERVE_RATIO = 0.05          # 5%  — 预留缓冲


@dataclass
class BudgetUsage:
    """各区域 Token 使用量快照"""
    system_prompt: int = 0
    memory: int = 0
    history: int = 0
    tool_results: int = 0
    total_used: int = 0
    context_window: int = 0

    @property
    def utilization(self) -> float:
        """上下文利用率 (0.0 ~ 1.0)"""
        if self.context_window <= 0:
            return 0.0
        return self.total_used / self.context_window

    @property
    def available(self) -> int:
        """剩余可用 Token"""
        return max(0, self.context_window - self.total_used)

    def to_dict(self) -> Dict:
        return {
            "system_prompt": self.system_prompt,
            "memory": self.memory,
            "history": self.history,
            "tool_results": self.tool_results,
            "total_used": self.total_used,
            "context_window": self.context_window,
            "utilization": round(self.utilization, 4),
            "available": self.available,
        }


class TokenBudget:
    """Token 预算管理器

    核心职责：
    1. 追踪上下文窗口内各区域的 Token 消耗
    2. 判断是否触发 Layer1/Layer2 压缩
    3. 提供预算超限警告

    使用方式：
        budget = TokenBudget(context_window=128000)
        budget.allocate(system_prompt_tokens=5000)
        budget.track("history", user_msg_tokens)
        if budget.should_compact_layer1():
            ...
    """

    def __init__(self, context_window: int, config: Optional[Dict] = None):
        """
        Args:
            context_window: 模型上下文窗口大小 (tokens)
            config: 压缩配置（来自 .ai/settings.json 的 compaction 节）
        """
        self.context_window = context_window

        # 从配置加载阈值，缺省用默认值
        cfg = config or {}
        self.layer1_trigger = cfg.get("layer1_trigger", 0.50)
        self.layer2_trigger = cfg.get("layer2_trigger", 0.80)
        self.warn_threshold = cfg.get("warn_threshold", 0.85)
        self.hard_limit = cfg.get("hard_limit", 0.95)
        self.tool_result_threshold = cfg.get("tool_result_threshold", 2000)

        # 各区域累计 Token
        self._system_prompt: int = 0
        self._memory: int = 0
        self._history: int = 0
        self._tool_results: int = 0

        # 预算上限（按比例）
        self._sp_budget = int(context_window * SYSTEM_PROMPT_RATIO)
        self._mem_budget = int(context_window * MEMORY_RATIO)
        self._hist_budget = int(context_window * HISTORY_RATIO)
        self._tool_budget = int(context_window * TOOL_RESULT_RATIO)
        self._reserve = int(context_window * RESERVE_RATIO)

        logger.debug(
            f"TokenBudget initialized: window={context_window}, "
            f"L1={self.layer1_trigger}, L2={self.layer2_trigger}"
        )

    # ──── 分配与追踪 ────

    def allocate(self, system_prompt: int = 0, memory: int = 0) -> None:
        """初始分配：系统提示词和记忆的 Token 占位

        在 session 启动时调用一次。
        """
        self._system_prompt = system_prompt
        self._memory = memory
        logger.debug(
            f"Budget allocated: SP={system_prompt}, MEM={memory}, "
            f"total={self.used}"
        )

    def track(self, category: str, tokens: int) -> None:
        """追踪某个区域的 Token 消耗

        Args:
            category: "history" | "tool_results"
            tokens:   增加的 Token 数
        """
        if category == "history":
            self._history += tokens
        elif category == "tool_results":
            self._tool_results += tokens
        elif category == "memory":
            self._memory += tokens
        else:
            logger.warning(f"Unknown budget category: {category}")

    def deduct(self, category: str, tokens: int) -> None:
        """扣减某个区域的 Token（压缩后减少）"""
        if category == "history":
            self._history = max(0, self._history - tokens)
        elif category == "tool_results":
            self._tool_results = max(0, self._tool_results - tokens)
        elif category == "memory":
            self._memory = max(0, self._memory - tokens)

    # ──── 状态查询 ────

    @property
    def used(self) -> int:
        """已使用 Token 总量"""
        return self._system_prompt + self._memory + self._history + self._tool_results

    @property
    def utilization(self) -> float:
        """上下文利用率 (0.0 ~ 1.0)"""
        if self.context_window <= 0:
            return 0.0
        return self.used / self.context_window

    @property
    def available(self) -> int:
        """剩余可用 Token（含预留）"""
        return max(0, self.context_window - self.used)

    def snapshot(self) -> BudgetUsage:
        """获取当前预算使用快照"""
        return BudgetUsage(
            system_prompt=self._system_prompt,
            memory=self._memory,
            history=self._history,
            tool_results=self._tool_results,
            total_used=self.used,
            context_window=self.context_window,
        )

    # ──── 压缩触发判断 ────

    def should_compact_layer1(self) -> bool:
        """是否需要 Layer1 压缩（实时，工具输出超阈值时）

        触发条件：
        - 上下文利用率 > layer1_trigger (默认 50%)
        - 或单条工具输出 > tool_result_threshold (默认 2000 字符)
        """
        return self.utilization > self.layer1_trigger

    def should_compact_layer2(self) -> bool:
        """是否需要 Layer2 归档（触发新 session）

        触发条件：上下文利用率 > layer2_trigger (默认 80%)
        """
        return self.utilization > self.layer2_trigger

    def should_warn(self) -> bool:
        """是否需要警告 AI 加速收尾

        触发条件：上下文利用率 > warn_threshold (默认 85%)
        """
        return self.utilization > self.warn_threshold

    def is_hard_limit(self) -> bool:
        """是否已达到硬限制

        触发条件：上下文利用率 > hard_limit (默认 95%)
        此时必须立即压缩或归档。
        """
        return self.utilization > self.hard_limit

    def tool_output_exceeds_threshold(self, content: str) -> bool:
        """单条工具输出是否超过阈值（字符数近似判断）

        Args:
            content: 工具输出内容
        """
        return len(content) > self.tool_result_threshold

    # ──── 预算检查（消息发送前） ────

    def can_afford(self, estimated_tokens: int) -> bool:
        """预估的消息是否能放入预算

        Args:
            estimated_tokens: 预估的新增 Token 数
        """
        return (self.used + estimated_tokens) < (self.context_window * self.hard_limit)

    def recommend_action(self) -> str:
        """根据当前利用率推荐操作

        Returns:
            "ok" | "layer1" | "layer2" | "warn" | "hard_limit"
        """
        u = self.utilization
        if u > self.hard_limit:
            return "hard_limit"
        elif u > self.warn_threshold:
            return "warn"
        elif u > self.layer2_trigger:
            return "layer2"
        elif u > self.layer1_trigger:
            return "layer1"
        return "ok"

    # ──── 输出 ────

    def summary(self) -> str:
        """人类可读的预算摘要"""
        snap = self.snapshot()
        pct = snap.utilization * 100
        action = self.recommend_action()
        return (
            f"Token Budget: {snap.total_used:,}/{snap.context_window:,} "
            f"({pct:.1f}%) — action: {action}\n"
            f"  SP={snap.system_prompt:,}  MEM={snap.memory:,}  "
            f"HIST={snap.history:,}  TOOL={snap.tool_results:,}  "
            f"AVAIL={snap.available:,}"
        )


def estimate_tokens(text: str) -> int:
    """简单的 Token 估算

    规则：
    - 英文：约 4 字符/token
    - 中文：约 2 字符/token
    - 混合：按中文字符比例加权

    Args:
        text: 待估算文本

    Returns:
        估算的 Token 数
    """
    if not text:
        return 0

    # 统计中文字符数
    chinese_chars = sum(1 for c in text if '\u4e00' <= c <= '\u9fff')
    total_chars = len(text)
    non_chinese = total_chars - chinese_chars

    # 中文按 2 字符/token，其他按 4 字符/token
    estimated = (chinese_chars / 2) + (non_chinese / 4)
    return max(1, int(estimated))


def load_budget_config(project_root: str) -> Dict:
    """从 .ai/settings.json 加载 compaction 配置

    Args:
        project_root: 项目根目录

    Returns:
        compaction 配置字典
    """
    settings_path = Path(project_root) / ".ai" / "settings.json"
    if settings_path.exists():
        try:
            data = json.loads(settings_path.read_text(encoding="utf-8"))
            return data.get("compaction", {})
        except (json.JSONDecodeError, OSError) as e:
            logger.warning(f"Failed to load settings.json: {e}")
    return {}


# ═══════════════════════════════════════════════════════════
# 单元测试
# ═══════════════════════════════════════════════════════════

if __name__ == "__main__":
    from log_config import configure_standalone_logging
    configure_standalone_logging()

    # 基础测试
    budget = TokenBudget(context_window=128000)

    # 初始分配
    budget.allocate(system_prompt=5000, memory=3000)
    print(budget.summary())

    # 模拟对话
    for i in range(10):
        budget.track("history", 800)
        budget.track("tool_results", 500)
        if i % 3 == 0:
            print(f"  Turn {i+1}: {budget.summary()}")

    # 检查触发条件
    print(f"\nLayer1 trigger: {budget.should_compact_layer1()}")
    print(f"Layer2 trigger: {budget.should_compact_layer2()}")
    print(f"Recommend: {budget.recommend_action()}")

    # Token 估算测试
    en_text = "Hello, this is a test of token estimation."
    zh_text = "你好，这是一个 Token 估算测试。"
    print(f"\nEN estimate: '{en_text}' → {estimate_tokens(en_text)} tokens")
    print(f"ZH estimate: '{zh_text}' → {estimate_tokens(zh_text)} tokens")
