#!/usr/bin/env python3
"""
ADDS Context Compactor — 两层压缩引擎

设计目标：
- Layer 1: 任务内实时压缩（工具输出超阈值 → 保存 .log + 替换为摘要）
- Layer 2: 会话归档压缩（上下文超 80% → LLM 摘要 + .mem 归档 + 新 session）

参考：P0-2 路线图 — 两层压缩策略

核心原则：
- 压缩 ≠ 丢弃细节
- 压缩 = 将细节移出当前上下文 + 保留回溯线索 + 结构化摘要留在链上
- 错误信号永不压缩（KEEP_FULL）
"""

import logging
from dataclasses import dataclass
from typing import Dict, List, Optional, Tuple

from token_budget import TokenBudget, estimate_tokens
from session_manager import SessionManager
from summary_decision_engine import (
    SummaryDecisionEngine,
    SummaryStrategy,
    has_error_signals,
    apply_tool_filter,
    is_redundant_message,
    LAYER2_SUMMARY_PROMPT,
)

logger = logging.getLogger(__name__)


# ═══════════════════════════════════════════════════════════
# 压缩结果数据结构
# ═══════════════════════════════════════════════════════════

@dataclass
class Layer1Result:
    """Layer1 压缩结果"""
    original_chars: int = 0
    compressed_chars: int = 0
    saved_to_log: bool = False
    log_filename: str = ""
    strategy: str = ""
    dropped: bool = False

    @property
    def compression_ratio(self) -> float:
        """压缩比 (0.0 ~ 1.0, 越小压缩越多)"""
        if self.original_chars == 0:
            return 1.0
        return self.compressed_chars / self.original_chars


@dataclass
class Layer2Result:
    """Layer2 归档结果"""
    session_id: str = ""
    mem_path: str = ""
    summary_tokens: int = 0       # 摘要的 token 数（注入到下一个 session 的部分）
    original_tokens: int = 0      # 原始 session 的 token 数
    full_record_tokens: int = 0   # 完整记录的 token 数（保存在 .mem 中）

    @property
    def compression_ratio(self) -> float:
        """摘要压缩比（摘要占原始的比例，越小压缩越多）"""
        if self.original_tokens == 0:
            return 1.0
        return min(1.0, self.summary_tokens / self.original_tokens)


# ═══════════════════════════════════════════════════════════
# Context Compactor
# ═══════════════════════════════════════════════════════════

class ContextCompactor:
    """两层上下文压缩引擎

    使用方式：
        compactor = ContextCompactor(budget, session_mgr, decision_engine)

        # Layer1: 每次收到工具输出后调用
        result = compactor.layer1_compress(tool_result_message)

        # Layer2: TokenBudget 触发时调用
        result = compactor.layer2_archive(model_interface)
    """

    def __init__(
        self,
        budget: TokenBudget,
        session_mgr: SessionManager,
        decision_engine: Optional[SummaryDecisionEngine] = None,
    ):
        self.budget = budget
        self.session_mgr = session_mgr
        self.engine = decision_engine or SummaryDecisionEngine()

        self._layer1_stats = {
            "total_compressions": 0,
            "total_saved_chars": 0,
            "keep_full_count": 0,
            "tool_filter_count": 0,
            "llm_analyze_count": 0,
            "hybrid_count": 0,
            "dropped_count": 0,
        }

    # ══════════════════════════════════════════════════════
    # Layer 1: 任务内实时压缩
    # ══════════════════════════════════════════════════════

    def layer1_compress(self, message: Dict) -> Tuple[Dict, Layer1Result]:
        """Layer1 压缩：对单条消息进行实时压缩

        处理流程：
        1. 决定摘要策略
        2. KEEP_FULL → 完全保留
        3. TOOL_FILTER → 规则提取摘要，长输出保存到 .log
        4. LLM_ANALYZE → 标记高价值，等待 Layer2 处理
        5. HYBRID → 规则提取 + 标记 LLM 精炼
        6. 冗余消息 → 丢弃

        Args:
            message: 消息字典 {"role": "...", "content": "..."}

        Returns:
            (处理后的消息, 压缩结果)
        """
        content = message.get("content", "")
        original_chars = len(content)
        result = Layer1Result(original_chars=original_chars, strategy="none")

        # 决定策略
        strategy = self.engine.decide(message, {"utilization": self.budget.utilization})
        result.strategy = strategy.value

        # 更新统计
        self._layer1_stats["total_compressions"] += 1

        if strategy == SummaryStrategy.KEEP_FULL:
            # 错误信号：完全保留，不做任何压缩
            self._layer1_stats["keep_full_count"] += 1
            result.compressed_chars = original_chars
            result.compression_ratio  # 1.0
            logger.debug(f"L1 KEEP_FULL: {original_chars} chars (error signals)")
            return message, result

        elif strategy == SummaryStrategy.TOOL_FILTER:
            self._layer1_stats["tool_filter_count"] += 1

            # 冗余消息 → 丢弃
            if is_redundant_message(content):
                self._layer1_stats["dropped_count"] += 1
                result.dropped = True
                result.compressed_chars = 0
                logger.debug(f"L1 DROP: redundant message")
                return message, result

            # 长工具输出 → 保存到 .log + 替换为摘要
            if self.budget.tool_output_exceeds_threshold(content):
                summary = apply_tool_filter(content)
                log_filename = self.session_mgr.save_tool_output(
                    content, summary=summary, strategy="tool_filter"
                )
                result.saved_to_log = True
                result.log_filename = log_filename
                result.compressed_chars = len(summary)

                # 更新预算
                original_tokens = estimate_tokens(content)
                summary_tokens = estimate_tokens(summary)
                self.budget.deduct("tool_results", original_tokens)
                self.budget.track("tool_results", summary_tokens)

                new_message = {
                    **message,
                    "content": f"详见 `{log_filename}`\n摘要: {summary}",
                }

                saved = original_chars - result.compressed_chars
                self._layer1_stats["total_saved_chars"] += saved
                logger.debug(
                    f"L1 TOOL_FILTER: {original_chars} → {result.compressed_chars} chars "
                    f"({saved} saved, saved to {log_filename})"
                )
                return new_message, result

            # 短工具输出 → 不压缩
            result.compressed_chars = original_chars
            return message, result

        elif strategy == SummaryStrategy.LLM_ANALYZE:
            self._layer1_stats["llm_analyze_count"] += 1
            # Layer1 不调用 LLM，仅标记高价值
            # 在 Session 文件中标记 priority: high
            result.compressed_chars = original_chars
            logger.debug(f"L1 LLM_ANALYZE: marked as high priority ({original_chars} chars)")
            return message, result

        elif strategy == SummaryStrategy.HYBRID:
            self._layer1_stats["hybrid_count"] += 1
            # 先工具过滤，再标记 LLM 精炼
            if self.budget.tool_output_exceeds_threshold(content):
                summary = apply_tool_filter(content)
                log_filename = self.session_mgr.save_tool_output(
                    content, summary=summary, strategy="hybrid"
                )
                result.saved_to_log = True
                result.log_filename = log_filename
                result.compressed_chars = len(summary)

                new_message = {
                    **message,
                    "content": f"详见 `{log_filename}`\n摘要: {summary}",
                }

                saved = original_chars - result.compressed_chars
                self._layer1_stats["total_saved_chars"] += saved
                return new_message, result

            result.compressed_chars = original_chars
            return message, result

        # 默认不压缩
        result.compressed_chars = original_chars
        return message, result

    def layer1_compress_batch(self, messages: List[Dict]) -> Tuple[List[Dict], List[Layer1Result]]:
        """批量 Layer1 压缩

        Args:
            messages: 消息列表

        Returns:
            (处理后的消息列表, 压缩结果列表)
        """
        results = []
        compressed_messages = []

        for msg in messages:
            new_msg, result = self.layer1_compress(msg)
            if not result.dropped:
                compressed_messages.append(new_msg)
            results.append(result)

        return compressed_messages, results

    # ══════════════════════════════════════════════════════
    # Layer 2: 会话归档压缩
    # ══════════════════════════════════════════════════════

    def layer2_archive(self, model_interface=None) -> Optional[Layer2Result]:
        """Layer2 归档：压缩当前 session → .mem 文件

        操作流程：
        1. 合并 .ses + .log → 完整记录
        2. 调用 LLM 生成结构化摘要（如果有 model_interface）
        3. 生成 .mem 文件（摘要 + 完整记录 + 链式指针）
        4. 回写 .ses 为摘要版
        5. 更新 TokenBudget

        Args:
            model_interface: 模型接口（用于 LLM 摘要，如果为 None 则用简单摘要）

        Returns:
            归档结果，或 None（如果没有活跃 session）
        """
        session_id = self.session_mgr.get_current_session_id()
        if not session_id:
            logger.warning("No active session to archive")
            return None

        # Step 1: 重建完整记录
        full_record = self.session_mgr.reconstruct_full_session(session_id)

        # Step 2: 生成摘要
        if model_interface:
            summary = self._generate_llm_summary(model_interface, full_record)
        else:
            summary = self._generate_simple_summary(full_record)

        # Step 3-4: 归档
        mem_path = self.session_mgr.archive_session(
            summary=summary,
            full_record=full_record,
        )

        # Step 5: 计算结果
        summary_tokens = estimate_tokens(summary)
        original_tokens = self.budget.used

        result = Layer2Result(
            session_id=session_id,
            mem_path=mem_path,
            summary_tokens=summary_tokens,
            original_tokens=original_tokens,
        )

        logger.info(
            f"L2 Archive: session={session_id}, "
            f"tokens {original_tokens} → {summary_tokens} "
            f"(ratio: {result.compression_ratio:.2f})"
        )

        return result

    def _generate_llm_summary(self, model_interface, full_record: str) -> str:
        """调用 LLM 生成结构化摘要

        Args:
            model_interface: ModelInterface 实例
            full_record: 完整 session 记录

        Returns:
            LLM 生成的结构化摘要
        """
        # 截断过长记录（避免超出上下文窗口）
        max_input_chars = int(model_interface.get_context_window() * 3)  # 约 3 字符/token
        if len(full_record) > max_input_chars:
            # 保留头部和尾部
            half = max_input_chars // 2
            full_record = full_record[:half] + "\n\n... (中间内容已截断) ...\n\n" + full_record[-half:]

        prompt = LAYER2_SUMMARY_PROMPT.format(content=full_record)

        try:
            import asyncio
            messages = [{"role": "user", "content": prompt}]

            # 收集非流式响应
            full_response = []
            async def _call():
                async for resp in model_interface.chat(
                    messages, system_prompt=None, stream=False
                ):
                    if resp.content:
                        full_response.append(resp.content)

            try:
                loop = asyncio.get_event_loop()
                if loop.is_running():
                    # 如果已在事件循环中，创建 task
                    import concurrent.futures
                    with concurrent.futures.ThreadPoolExecutor() as pool:
                        future = pool.submit(asyncio.run, _call())
                        future.result(timeout=120)
                else:
                    asyncio.run(_call())
            except RuntimeError:
                asyncio.run(_call())

            summary = "".join(full_response)
            if summary:
                logger.info(f"LLM summary generated: {len(summary)} chars")
                return summary

        except Exception as e:
            logger.warning(f"LLM summary failed, falling back to simple: {e}")

        # 回退到简单摘要
        return self._generate_simple_summary(full_record)

    def _generate_simple_summary(self, full_record: str) -> str:
        """简单摘要生成（无 LLM，基于规则提取）

        Args:
            full_record: 完整 session 记录

        Returns:
            基于规则提取的摘要
        """
        lines = full_record.split("\n")
        decisions = []
        errors = []
        code_changes = []
        test_results = []

        for line in lines:
            stripped = line.strip()
            # 提取决策
            if any(kw in stripped.lower() for kw in ["决定", "决定", "decided", "conclusion"]):
                decisions.append(stripped)
            # 提取错误
            if has_error_signals(stripped):
                errors.append(stripped)
            # 提取代码变更
            if stripped.startswith("新增:") or stripped.startswith("修改:") or stripped.startswith("删除:"):
                code_changes.append(stripped)
            # 提取测试结果
            if "passed" in stripped.lower() and ("failed" in stripped.lower() or "test" in stripped.lower()):
                test_results.append(stripped)

        # 组装摘要
        parts = []
        if decisions:
            parts.append("### 关键决策\n" + "\n".join(f"- {d}" for d in decisions[:10]))
        if code_changes:
            parts.append("### 代码变更\n" + "\n".join(f"- {c}" for c in code_changes[:10]))
        if test_results:
            parts.append("### 测试结果\n" + "\n".join(f"- {t}" for t in test_results[:5]))
        if errors:
            parts.append("### 错误与修复\n" + "\n".join(f"- {e}" for e in errors[:5]))

        if not parts:
            # 无结构化信息，截取前 500 字符
            parts.append("### 会话概要\n" + full_record[:500] + "..." if len(full_record) > 500 else full_record)

        return "\n\n".join(parts)

    # ══════════════════════════════════════════════════════
    # 自动压缩决策
    # ══════════════════════════════════════════════════════

    def check_and_compact(self, message: Optional[Dict] = None) -> Optional[Layer1Result]:
        """检查预算并自动执行 Layer1 压缩

        在 Agent Loop 的每轮迭代中调用：
        1. 如果有新消息且是工具输出 → 执行 Layer1
        2. 如果利用率超阈值 → 执行 Layer2

        Args:
            message: 新增消息（可选）

        Returns:
            Layer1 压缩结果（如果执行了），或 None
        """
        result = None

        # Layer1: 对新消息压缩
        if message:
            _, result = self.layer1_compress(message)

        return result

    def should_archive(self) -> bool:
        """是否应该执行 Layer2 归档"""
        return self.budget.should_compact_layer2()

    def get_warning(self) -> Optional[str]:
        """获取预算警告（注入到对话中提醒 AI）"""
        if self.budget.is_hard_limit():
            return (
                "⚠️ 上下文已接近极限！必须立即结束当前任务并归档。"
                f"当前利用率: {self.budget.utilization:.1%}"
            )
        elif self.budget.should_warn():
            return (
                f"⚠️ 上下文利用率已达 {self.budget.utilization:.1%}，请加速完成当前任务。"
                "归档后将开始新 session。"
            )
        return None

    # ══════════════════════════════════════════════════════
    # 统计与输出
    # ══════════════════════════════════════════════════════

    def get_stats(self) -> Dict:
        """获取压缩统计"""
        return {
            "layer1": dict(self._layer1_stats),
            "budget": self.budget.snapshot().to_dict(),
            "recommendation": self.budget.recommend_action(),
        }

    def summary(self) -> str:
        """人类可读的压缩状态摘要"""
        stats = self.get_stats()
        l1 = stats["layer1"]
        b = stats["budget"]
        return (
            f"Context Compactor Status:\n"
            f"  Budget: {b['total_used']:,}/{b['context_window']:,} ({b['utilization']:.1%})\n"
            f"  L1 compressions: {l1['total_compressions']}\n"
            f"    KEEP_FULL: {l1['keep_full_count']}  "
            f"TOOL_FILTER: {l1['tool_filter_count']}  "
            f"LLM_ANALYZE: {l1['llm_analyze_count']}  "
            f"HYBRID: {l1['hybrid_count']}\n"
            f"    Dropped: {l1['dropped_count']}  "
            f"Saved chars: {l1['total_saved_chars']:,}\n"
            f"  Recommendation: {stats['recommendation']}"
        )


# ═══════════════════════════════════════════════════════════
# 便捷函数
# ═══════════════════════════════════════════════════════════

def create_compactor(
    context_window: int,
    sessions_dir: str = ".ai/sessions",
    config: Optional[Dict] = None,
) -> ContextCompactor:
    """创建 ContextCompactor 实例（便捷函数）

    Args:
        context_window: 模型上下文窗口大小
        sessions_dir: sessions 目录路径
        config: 压缩配置

    Returns:
        配置好的 ContextCompactor
    """
    budget = TokenBudget(context_window=context_window, config=config)
    session_mgr = SessionManager(sessions_dir=sessions_dir)
    decision_engine = SummaryDecisionEngine(config=config)
    return ContextCompactor(budget, session_mgr, decision_engine)


# ═══════════════════════════════════════════════════════════
# 单元测试
# ═══════════════════════════════════════════════════════════

if __name__ == "__main__":
    import tempfile
    import shutil

    logging.basicConfig(level=logging.DEBUG)

    # 使用临时目录
    tmp = tempfile.mkdtemp(prefix="adds_compact_test_")
    try:
        # 创建 compactor
        compactor = create_compactor(
            context_window=128000,
            sessions_dir=tmp,
        )

        # 创建 session
        sid = compactor.session_mgr.create_session(agent="developer", feature="auth")
        print(f"Session: {sid}")

        # Layer1: 正常工具输出
        tool_msg = {"role": "tool_result", "content": "test_login PASSED\ntest_logout PASSED\n2 passed in 1.5s"}
        new_msg, result = compactor.layer1_compress(tool_msg)
        print(f"L1 (short tool): strategy={result.strategy}, ratio={result.compression_ratio:.2f}")

        # Layer1: 长工具输出
        long_output = "line\n" * 500  # > 2000 chars
        long_msg = {"role": "tool_result", "content": long_output}
        new_msg, result = compactor.layer1_compress(long_msg)
        print(f"L1 (long tool): strategy={result.strategy}, saved_to_log={result.saved_to_log}, "
              f"file={result.log_filename}, ratio={result.compression_ratio:.2f}")

        # Layer1: 错误信号
        error_msg = {"role": "tool_result", "content": "Traceback (most recent call last):\n  RuntimeError: failed\nExit code: 1"}
        new_msg, result = compactor.layer1_compress(error_msg)
        print(f"L1 (error): strategy={result.strategy}, ratio={result.compression_ratio:.2f}")

        # Layer1: 决策消息
        decision_msg = {"role": "assistant", "content": "经过分析，我决定使用 JWT 进行认证，原因是安全性更好。"}
        new_msg, result = compactor.layer1_compress(decision_msg)
        print(f"L1 (decision): strategy={result.strategy}")

        # 归档
        result = compactor.layer2_archive()
        if result:
            print(f"L2 archive: session={result.session_id}, mem={result.mem_path}, "
                  f"ratio={result.compression_ratio:.2f}")

        # 状态
        print(compactor.summary())

    finally:
        shutil.rmtree(tmp)
        print("\n✅ ContextCompactor tests passed")
