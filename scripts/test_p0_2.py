#!/usr/bin/env python3
"""
P0-2 单元测试: Token 预算 + Session 管理 + 摘要决策 + 上下文压缩
"""

import asyncio
import shutil
import tempfile
import unittest
from datetime import datetime
from pathlib import Path

from token_budget import (
    TokenBudget, BudgetUsage, estimate_tokens, load_budget_config,
    SYSTEM_PROMPT_RATIO, MEMORY_RATIO, HISTORY_RATIO, TOOL_RESULT_RATIO, RESERVE_RATIO,
)
from session_manager import SessionManager, SessionHeader, MemoryHeader
from summary_decision_engine import (
    SummaryDecisionEngine, SummaryStrategy,
    has_error_signals, extract_error_context, is_redundant_message,
    has_decision_keywords, apply_tool_filter, tool_filter_pytest,
)
from context_compactor import (
    ContextCompactor, Layer1Result, Layer2Result, create_compactor,
)


class TestTokenBudget(unittest.TestCase):
    """TokenBudget 单元测试"""

    def test_init_default_thresholds(self):
        budget = TokenBudget(context_window=128000)
        self.assertEqual(budget.context_window, 128000)
        self.assertEqual(budget.layer1_trigger, 0.50)
        self.assertEqual(budget.layer2_trigger, 0.80)
        self.assertEqual(budget.warn_threshold, 0.85)
        self.assertEqual(budget.hard_limit, 0.95)

    def test_init_custom_config(self):
        budget = TokenBudget(context_window=8000, config={
            "layer1_trigger": 0.3, "layer2_trigger": 0.7,
        })
        self.assertEqual(budget.layer1_trigger, 0.3)
        self.assertEqual(budget.layer2_trigger, 0.7)

    def test_allocate(self):
        budget = TokenBudget(context_window=10000)
        budget.allocate(system_prompt=1500, memory=1000)
        self.assertEqual(budget._system_prompt, 1500)
        self.assertEqual(budget._memory, 1000)

    def test_track(self):
        budget = TokenBudget(context_window=10000)
        budget.track("history", 500)
        budget.track("tool_results", 300)
        self.assertEqual(budget._history, 500)
        self.assertEqual(budget._tool_results, 300)

    def test_deduct(self):
        budget = TokenBudget(context_window=10000)
        budget.track("history", 500)
        budget.deduct("history", 200)
        self.assertEqual(budget._history, 300)

    def test_deduct_floor_zero(self):
        budget = TokenBudget(context_window=10000)
        budget.track("history", 100)
        budget.deduct("history", 200)
        self.assertEqual(budget._history, 0)

    def test_utilization(self):
        budget = TokenBudget(context_window=10000)
        budget.allocate(system_prompt=1000, memory=500)
        budget.track("history", 2000)
        # used = 1000 + 500 + 2000 = 3500
        self.assertAlmostEqual(budget.utilization, 0.35)

    def test_available(self):
        budget = TokenBudget(context_window=10000)
        budget.allocate(system_prompt=1000)
        self.assertEqual(budget.available, 9000)

    def test_should_compact_layer1(self):
        budget = TokenBudget(context_window=10000)
        budget.track("history", 6000)
        self.assertTrue(budget.should_compact_layer1())

    def test_should_compact_layer2(self):
        budget = TokenBudget(context_window=10000)
        budget.track("history", 8500)
        self.assertTrue(budget.should_compact_layer2())

    def test_should_warn(self):
        budget = TokenBudget(context_window=10000)
        budget.track("history", 9000)
        self.assertTrue(budget.should_warn())

    def test_is_hard_limit(self):
        budget = TokenBudget(context_window=10000)
        budget.track("history", 9600)
        self.assertTrue(budget.is_hard_limit())

    def test_tool_output_exceeds_threshold(self):
        budget = TokenBudget(context_window=10000)
        self.assertTrue(budget.tool_output_exceeds_threshold("x" * 3000))
        self.assertFalse(budget.tool_output_exceeds_threshold("short"))

    def test_can_afford(self):
        budget = TokenBudget(context_window=10000)
        budget.track("history", 5000)
        self.assertTrue(budget.can_afford(3000))
        self.assertFalse(budget.can_afford(5000))

    def test_recommend_action(self):
        budget = TokenBudget(context_window=10000)
        self.assertEqual(budget.recommend_action(), "ok")
        budget.track("history", 6000)
        self.assertEqual(budget.recommend_action(), "layer1")
        budget.track("history", 2500)
        self.assertEqual(budget.recommend_action(), "layer2")

    def test_snapshot(self):
        budget = TokenBudget(context_window=10000)
        budget.allocate(system_prompt=1000, memory=500)
        snap = budget.snapshot()
        self.assertIsInstance(snap, BudgetUsage)
        self.assertEqual(snap.system_prompt, 1000)
        self.assertEqual(snap.memory, 500)

    def test_ratio_sum(self):
        """预算比例之和应接近 1.0"""
        total = SYSTEM_PROMPT_RATIO + MEMORY_RATIO + HISTORY_RATIO + TOOL_RESULT_RATIO + RESERVE_RATIO
        self.assertAlmostEqual(total, 1.0)


class TestEstimateTokens(unittest.TestCase):
    """estimate_tokens 单元测试"""

    def test_empty_string(self):
        self.assertEqual(estimate_tokens(""), 0)

    def test_english_text(self):
        tokens = estimate_tokens("Hello, this is a test.")
        self.assertGreater(tokens, 0)

    def test_chinese_text(self):
        tokens = estimate_tokens("你好，这是一个测试。")
        self.assertGreater(tokens, 0)

    def test_chinese_more_tokens_than_english(self):
        """中文比英文同长度需要更多 token"""
        zh_tokens = estimate_tokens("你好你好你好你好你好你好你好你好你好你好")  # 20 chars
        en_tokens = estimate_tokens("aaaaaaaaaaaaaaaaaaaa")  # 20 chars
        # 中文每 2 字符 ≈ 1 token，英文每 4 字符 ≈ 1 token
        self.assertGreater(zh_tokens, en_tokens)


class TestSessionManager(unittest.TestCase):
    """SessionManager 单元测试"""

    def setUp(self):
        self.tmp = tempfile.mkdtemp(prefix="adds_test_session_")
        self.mgr = SessionManager(sessions_dir=self.tmp)

    def tearDown(self):
        shutil.rmtree(self.tmp)

    def test_create_session(self):
        sid = self.mgr.create_session(agent="developer", feature="auth")
        self.assertIsNotNone(sid)
        self.assertTrue(self.mgr.session_exists(sid))

    def test_create_session_files(self):
        sid = self.mgr.create_session(agent="developer", feature="auth")
        ses_path = Path(self.tmp) / f"{sid}.ses"
        self.assertTrue(ses_path.exists())

    def test_append_message(self):
        sid = self.mgr.create_session(agent="developer", feature="auth")
        self.mgr.append_message("user", "Hello")
        _, body = self.mgr.read_session(sid)
        self.assertIn("Hello", body)

    def test_save_tool_output(self):
        sid = self.mgr.create_session(agent="developer", feature="auth")
        log_file = self.mgr.save_tool_output("tool output content", summary="2 passed")
        self.assertTrue(log_file.endswith(".log"))
        log_path = Path(self.tmp) / log_file
        self.assertTrue(log_path.exists())
        content = self.mgr.read_log(log_file)
        self.assertEqual(content, "tool output content")

    def test_archive_session(self):
        sid = self.mgr.create_session(agent="developer", feature="auth")
        self.mgr.append_message("user", "Implement auth")
        mem_path = self.mgr.archive_session(summary="### 关键决策\n- 使用 JWT")
        self.assertTrue(Path(mem_path).exists())
        # .ses should still exist
        self.assertTrue(self.mgr.session_exists(sid))

    def test_restore_session(self):
        sid = self.mgr.create_session(agent="developer", feature="auth")
        self.mgr.append_message("user", "Implement auth")
        self.mgr.archive_session(summary="JWT authentication decided")

        restored_path = self.mgr.restore_session(sid)
        self.assertTrue(Path(restored_path).exists())

    def test_chain_pointers(self):
        sid1 = self.mgr.create_session(agent="developer", feature="auth")
        self.mgr.archive_session(summary="Session 1 summary")

        # archive resets current session, need new session to check prev pointer
        sid2 = self.mgr.create_session(agent="developer", feature="dashboard")
        header2, _ = self.mgr.read_session(sid2)
        # prev_session should point to sid1
        self.assertEqual(header2.prev_session, sid1)

    def test_prev_session_summary(self):
        sid1 = self.mgr.create_session(agent="developer", feature="auth")
        self.mgr.append_message("user", "Use JWT for authentication")
        self.mgr.archive_session(summary="### 关键决策\n- Use JWT")

        sid2 = self.mgr.create_session(agent="developer", feature="dashboard")
        prev_summary = self.mgr.get_prev_session_summary()
        self.assertIsNotNone(prev_summary)
        self.assertIn("JWT", prev_summary)

    def test_list_sessions(self):
        self.mgr.create_session(agent="developer", feature="auth")
        self.mgr.create_session(agent="developer", feature="dashboard")
        sessions = self.mgr.list_sessions()
        self.assertGreaterEqual(len(sessions), 2)

    def test_session_header_roundtrip(self):
        header = SessionHeader(
            session_id="20260410-160000",
            agent="developer",
            feature="auth",
            created="2026-04-10T16:00:00",
            status="active",
            prev_session="20260410-150000",
        )
        metadata = header.to_metadata()
        parsed = SessionHeader.from_metadata(metadata)
        self.assertEqual(parsed.session_id, "20260410-160000")
        self.assertEqual(parsed.agent, "developer")
        self.assertEqual(parsed.prev_session, "20260410-150000")

    def test_reconstruct_full_session(self):
        sid = self.mgr.create_session(agent="developer", feature="auth")
        self.mgr.save_tool_output("Full tool output here", summary="Test passed")
        reconstructed = self.mgr.reconstruct_full_session(sid)
        self.assertIn("Full tool output here", reconstructed)


class TestSummaryDecisionEngine(unittest.TestCase):
    """SummaryDecisionEngine 单元测试"""

    def setUp(self):
        self.engine = SummaryDecisionEngine()

    def test_error_signal_keep_full(self):
        msg = {"role": "tool_result", "content": "Traceback: RuntimeError\nExit code: 1"}
        strategy = self.engine.decide(msg)
        self.assertEqual(strategy, SummaryStrategy.KEEP_FULL)

    def test_tool_result_tool_filter(self):
        msg = {"role": "tool_result", "content": "12 passed, 0 failed in 3.2s"}
        strategy = self.engine.decide(msg)
        self.assertEqual(strategy, SummaryStrategy.TOOL_FILTER)

    def test_decision_keywords_llm_analyze(self):
        msg = {"role": "assistant", "content": "经过分析，我决定使用 JWT 进行认证，原因是安全性更好。"}
        strategy = self.engine.decide(msg)
        self.assertEqual(strategy, SummaryStrategy.LLM_ANALYZE)

    def test_long_message_llm_analyze(self):
        msg = {"role": "assistant", "content": "x" * 600}
        strategy = self.engine.decide(msg)
        self.assertEqual(strategy, SummaryStrategy.LLM_ANALYZE)

    def test_high_utilization_tool_filter(self):
        engine = SummaryDecisionEngine()
        engine.context_utilization = 0.8
        msg = {"role": "assistant", "content": "Some content"}
        strategy = engine.decide(msg, {"utilization": 0.8})
        self.assertEqual(strategy, SummaryStrategy.TOOL_FILTER)

    def test_batch_decide(self):
        messages = [
            {"role": "tool_result", "content": "Error: failed"},
            {"role": "tool_result", "content": "12 passed"},
            {"role": "assistant", "content": "我决定使用 JWT"},
        ]
        strategies = self.engine.decide_batch(messages)
        self.assertEqual(len(strategies), 3)
        self.assertEqual(strategies[0], SummaryStrategy.KEEP_FULL)

    def test_has_error_signals(self):
        self.assertTrue(has_error_signals("RuntimeError: something failed"))
        self.assertTrue(has_error_signals("Traceback (most recent call last)"))
        self.assertTrue(has_error_signals("Exit code: 1"))
        self.assertFalse(has_error_signals("12 passed, 0 failed in 3.2s"))
        self.assertFalse(has_error_signals("All tests passed"))

    def test_error_signal_excludes_test_pass(self):
        """'0 failed' 不应被误判为错误信号"""
        self.assertFalse(has_error_signals("12 passed, 0 failed in 1.5s"))

    def test_extract_error_context(self):
        content = "line1\nline2\nError: something failed\nline4\nline5\nline6"
        ctx = extract_error_context(content, context_lines=1)
        self.assertIn("Error", ctx)
        self.assertIn("line2", ctx)

    def test_is_redundant_message(self):
        self.assertTrue(is_redundant_message("好的"))
        self.assertTrue(is_redundant_message("明白"))
        self.assertTrue(is_redundant_message("OK"))
        self.assertFalse(is_redundant_message("我已完成了功能实现"))

    def test_has_decision_keywords(self):
        self.assertTrue(has_decision_keywords("决定使用 JWT"))
        self.assertTrue(has_decision_keywords("We decided to use JWT"))
        self.assertFalse(has_decision_keywords("Implement the feature"))

    def test_tool_filter_pytest(self):
        result = tool_filter_pytest("2 passed, 1 failed in 1.5s")
        self.assertIn("2 passed", result)
        self.assertIn("1 failed", result)

    def test_apply_tool_filter(self):
        # 长内容
        result = apply_tool_filter("line\n" * 100)
        self.assertLess(len(result), 500)

    def test_layer1_action(self):
        msg = {"role": "tool_result", "content": "x" * 600}
        action = self.engine.get_layer1_action(msg, SummaryStrategy.TOOL_FILTER)
        self.assertEqual(action["strategy"], "tool_filter")


class TestContextCompactor(unittest.TestCase):
    """ContextCompactor 单元测试"""

    def setUp(self):
        self.tmp = tempfile.mkdtemp(prefix="adds_test_compact_")
        self.compactor = create_compactor(
            context_window=128000,
            sessions_dir=self.tmp,
        )
        self.compactor.session_mgr.create_session(agent="developer", feature="auth")

    def tearDown(self):
        shutil.rmtree(self.tmp)

    def test_layer1_keep_full(self):
        msg = {"role": "tool_result", "content": "Traceback: RuntimeError: failed\nExit code: 1"}
        new_msg, result = self.compactor.layer1_compress(msg)
        self.assertEqual(result.strategy, "keep_full")
        self.assertEqual(result.compression_ratio, 1.0)

    def test_layer1_tool_filter_short(self):
        msg = {"role": "tool_result", "content": "12 passed, 0 failed"}
        _, result = self.compactor.layer1_compress(msg)
        self.assertEqual(result.strategy, "tool_filter")
        # Short output not saved to log
        self.assertFalse(result.saved_to_log)

    def test_layer1_tool_filter_long(self):
        long_content = "line\n" * 500  # > 2000 chars
        msg = {"role": "tool_result", "content": long_content}
        _, result = self.compactor.layer1_compress(msg)
        self.assertEqual(result.strategy, "tool_filter")
        self.assertTrue(result.saved_to_log)
        self.assertNotEqual(result.log_filename, "")

    def test_layer1_llm_analyze(self):
        msg = {"role": "assistant", "content": "经过分析，我决定使用 JWT 进行认证，原因是安全性更好。"}
        _, result = self.compactor.layer1_compress(msg)
        self.assertEqual(result.strategy, "llm_analyze")

    def test_layer1_drop_redundant(self):
        msg = {"role": "assistant", "content": "好的"}
        _, result = self.compactor.layer1_compress(msg)
        self.assertTrue(result.dropped)

    def test_layer1_batch(self):
        messages = [
            {"role": "tool_result", "content": "Error: failed"},
            {"role": "tool_result", "content": "12 passed"},
            {"role": "assistant", "content": "好的"},
        ]
        compressed, results = self.compactor.layer1_compress_batch(messages)
        # "好的" should be dropped
        self.assertEqual(len(compressed), 2)

    def test_layer2_archive(self):
        self.compactor.session_mgr.append_message("user", "Implement JWT auth")
        result = self.compactor.layer2_archive()
        self.assertIsNotNone(result)
        self.assertIsInstance(result, Layer2Result)
        self.assertNotEqual(result.session_id, "")
        self.assertNotEqual(result.mem_path, "")
        self.assertGreater(result.compression_ratio, 0)
        self.assertLessEqual(result.compression_ratio, 1.0)

    def test_layer2_no_active_session(self):
        # Archive first
        self.compactor.layer2_archive()
        # Try again without new session
        result = self.compactor.layer2_archive()
        self.assertIsNone(result)

    def test_get_stats(self):
        stats = self.compactor.get_stats()
        self.assertIn("layer1", stats)
        self.assertIn("budget", stats)
        self.assertIn("recommendation", stats)

    def test_should_archive(self):
        # Default budget is low
        self.assertFalse(self.compactor.should_archive())

    def test_get_warning(self):
        # Default budget is low
        self.assertIsNone(self.compactor.get_warning())


if __name__ == "__main__":
    unittest.main()
