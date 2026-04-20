#!/usr/bin/env python3
"""
ADDS P1 测试 — Agent Loop 韧性增强

测试范围：
1. LoopStateMachine 状态机核心逻辑
2. 终止条件判定（7 种）
3. 继续条件判定（5 种）
4. 错误分类与恢复策略
5. 指数退避策略
6. PTL 恢复策略
7. max_output_tokens 恢复策略
8. AgentLoop 集成韧性机制
"""

import sys
import os
import logging
import pytest
from unittest.mock import AsyncMock, MagicMock, patch

sys.path.insert(0, os.path.dirname(__file__))

from loop_state import (
    LoopStateMachine, LoopState, ResilienceConfig,
    TerminationReason, ContinueReason, ErrorCategory,
    TERMINATION_DESCRIPTIONS, CONTINUE_DESCRIPTIONS,
)


# ═══════════════════════════════════════════════════════════
# 场景 1: LoopStateMachine 基础逻辑
# ═══════════════════════════════════════════════════════════

class TestLoopStateMachineBasic:
    """状态机基础逻辑测试"""

    def setup_method(self):
        self.sm = LoopStateMachine()

    def test_normal_stop_no_continue_no_terminate(self):
        """正常 stop → 不终止也不继续"""
        state = self.sm.evaluate_response("stop")
        assert not state.should_terminate
        assert not state.should_continue
        assert state.termination_reason is None
        assert state.continue_reason is None

    def test_streaming_no_action(self):
        """流式中 streaming → 不终止也不继续"""
        state = self.sm.evaluate_response("streaming")
        assert not state.should_terminate
        assert not state.should_continue

    def test_thinking_no_action(self):
        """思考中 thinking → 不终止也不继续"""
        state = self.sm.evaluate_response("thinking")
        assert not state.should_terminate
        assert not state.should_continue


# ═══════════════════════════════════════════════════════════
# 场景 2: 7 种终止条件
# ═══════════════════════════════════════════════════════════

class TestTerminationConditions:
    """7 种终止条件测试"""

    def setup_method(self):
        self.sm = LoopStateMachine()

    def test_user_abort_terminates(self):
        """用户中止 → ABORTED_STREAMING 终止"""
        state = self.sm.evaluate_response("stop", is_user_abort=True)
        assert state.should_terminate
        assert state.termination_reason == TerminationReason.ABORTED_STREAMING

    def test_hard_limit_ptl_exhausted(self):
        """Token 硬限制且 PTL 重试耗尽 → BLOCKING_LIMIT"""
        config = ResilienceConfig(ptl_max_retries=1)
        sm = LoopStateMachine(config=config)
        # 第一次 PTL 恢复
        state1 = sm.evaluate_response("stop", is_hard_limit=True)
        assert state1.should_continue
        assert state1.continue_reason == ContinueReason.PROMPT_TOO_LONG
        # 第二次 PTL 恢复耗尽
        state2 = sm.evaluate_response("stop", is_hard_limit=True)
        assert state2.should_terminate
        assert state2.termination_reason == TerminationReason.BLOCKING_LIMIT

    def test_model_error_finish(self):
        """finish_reason=error → MODEL_ERROR 终止"""
        state = self.sm.evaluate_response("error")
        assert state.should_terminate
        assert state.termination_reason == TerminationReason.MODEL_ERROR

    def test_content_filter_terminates(self):
        """内容过滤 → MODEL_ERROR 终止"""
        state = self.sm.evaluate_response("content_filter")
        assert state.should_terminate
        assert state.termination_reason == TerminationReason.MODEL_ERROR

    def test_system_error_terminates(self):
        """系统错误（MemoryError）→ 不重试，直接终止"""
        state = self.sm.evaluate_response("stop", error=MemoryError("OOM"))
        assert state.should_terminate
        assert state.termination_reason == TerminationReason.MODEL_ERROR
        assert state.error_category == ErrorCategory.SYSTEM

    def test_unknown_error_terminates(self):
        """未知错误 → 保守终止"""
        state = self.sm.evaluate_response("stop", error=Exception("Something weird"))
        assert state.should_terminate
        assert state.termination_reason == TerminationReason.MODEL_ERROR

    def test_ptl_413_exhausted(self):
        """413 错误且重试耗尽 → PROMPT_TOO_LONG"""
        config = ResilienceConfig(ptl_max_retries=1)
        sm = LoopStateMachine(config=config)
        # 第一次 PTL 恢复
        state1 = sm.evaluate_response("stop", error=Exception("HTTP 413: prompt_too_long"))
        assert state1.continue_reason == ContinueReason.PROMPT_TOO_LONG
        # 第二次 PTL 恢复耗尽
        state2 = sm.evaluate_response("stop", error=Exception("HTTP 413: prompt_too_long"))
        assert state2.should_terminate
        assert state2.termination_reason == TerminationReason.PROMPT_TOO_LONG


# ═══════════════════════════════════════════════════════════
# 场景 3: 5 种继续条件
# ═══════════════════════════════════════════════════════════

class TestContinueConditions:
    """5 种继续条件测试"""

    def setup_method(self):
        self.sm = LoopStateMachine()

    def test_normal_continue(self):
        """正常对话 → ContinueReason.NORMAL（不在 evaluate_response 中触发）"""
        # NORMAL 只在外层循环使用，evaluate_response 不返回它
        pass

    def test_max_output_tokens_continue(self):
        """length 截断 → MAX_OUTPUT_TOKENS 继续"""
        state = self.sm.evaluate_response("length")
        assert state.should_continue
        assert state.continue_reason == ContinueReason.MAX_OUTPUT_TOKENS
        assert state.max_output_tokens_count == 1

    def test_max_output_tokens_retry_limit(self):
        """length 截断最多重试 3 次"""
        config = ResilienceConfig(max_output_tokens_retries=3)
        sm = LoopStateMachine(config=config)
        for i in range(3):
            state = sm.evaluate_response("length")
            assert state.should_continue
        # 第 4 次 → 不再继续
        state = sm.evaluate_response("length")
        assert not state.should_continue

    def test_ptl_hard_limit_continue(self):
        """Token 硬限制 → PROMPT_TOO_LONG 继续"""
        state = self.sm.evaluate_response("stop", is_hard_limit=True)
        assert state.should_continue
        assert state.continue_reason == ContinueReason.PROMPT_TOO_LONG

    def test_error_retry_environment(self):
        """环境错误 → ERROR_RETRY 继续"""
        state = self.sm.evaluate_response("stop", error=ConnectionError("Network down"))
        assert state.should_continue
        assert state.continue_reason == ContinueReason.ERROR_RETRY
        assert state.error_category == ErrorCategory.ENVIRONMENT

    def test_error_retry_rate_limit(self):
        """429 速率限制 → ERROR_RETRY 继续"""
        state = self.sm.evaluate_response("stop", error=Exception("HTTP 429: rate limit"))
        assert state.should_continue
        assert state.continue_reason == ContinueReason.ERROR_RETRY

    def test_error_retry_exhausted(self):
        """环境错误重试耗尽 → MODEL_ERROR 终止"""
        config = ResilienceConfig(error_max_retries=2)
        sm = LoopStateMachine(config=config)
        for i in range(2):
            state = sm.evaluate_response("stop", error=ConnectionError("Network down"))
            assert state.should_continue
        # 第 3 次 → 终止
        state = sm.evaluate_response("stop", error=ConnectionError("Network down"))
        assert state.should_terminate
        assert state.termination_reason == TerminationReason.MODEL_ERROR


# ═══════════════════════════════════════════════════════════
# 场景 4: 错误分类
# ═══════════════════════════════════════════════════════════

class TestErrorClassification:
    """错误分类测试"""

    def setup_method(self):
        self.sm = LoopStateMachine()

    def test_connection_error_is_environment(self):
        assert self.sm._classify_error(ConnectionError()) == ErrorCategory.ENVIRONMENT

    def test_timeout_error_is_environment(self):
        assert self.sm._classify_error(TimeoutError()) == ErrorCategory.ENVIRONMENT

    def test_os_error_is_environment(self):
        assert self.sm._classify_error(OSError()) == ErrorCategory.ENVIRONMENT

    def test_keyboard_interrupt_is_user_abort(self):
        assert self.sm._classify_error(KeyboardInterrupt()) == ErrorCategory.USER_ABORT

    def test_memory_error_is_system(self):
        assert self.sm._classify_error(MemoryError()) == ErrorCategory.SYSTEM

    def test_http_413_is_model(self):
        assert self.sm._classify_error(Exception("HTTP 413")) == ErrorCategory.MODEL

    def test_http_429_is_model(self):
        assert self.sm._classify_error(Exception("HTTP 429")) == ErrorCategory.MODEL

    def test_http_500_is_model(self):
        assert self.sm._classify_error(Exception("HTTP 500")) == ErrorCategory.MODEL

    def test_context_length_is_model(self):
        assert self.sm._classify_error(Exception("context_length_exceeded")) == ErrorCategory.MODEL

    def test_network_keyword_is_environment(self):
        assert self.sm._classify_error(Exception("connection refused")) == ErrorCategory.ENVIRONMENT

    def test_unknown_exception(self):
        assert self.sm._classify_error(Exception("random error")) == ErrorCategory.UNKNOWN

    def test_413_triggers_ptl(self):
        """413 错误触发 PTL 恢复"""
        state = self.sm.evaluate_response("stop", error=Exception("HTTP 413: prompt_too_long"))
        assert state.continue_reason == ContinueReason.PROMPT_TOO_LONG

    def test_context_length_triggers_ptl(self):
        """context_length 错误触发 PTL 恢复"""
        state = self.sm.evaluate_response(
            "stop", error=Exception("This model's maximum context length is 8192 tokens")
        )
        assert state.continue_reason == ContinueReason.PROMPT_TOO_LONG


# ═══════════════════════════════════════════════════════════
# 场景 5: 指数退避策略
# ═══════════════════════════════════════════════════════════

class TestBackoffStrategy:
    """指数退避策略测试"""

    def test_backoff_increases(self):
        sm = LoopStateMachine(config=ResilienceConfig(error_backoff_base=1.0))
        b1 = sm.get_backoff_time(1)
        b2 = sm.get_backoff_time(2)
        b3 = sm.get_backoff_time(3)
        assert b1 < b2 < b3

    def test_backoff_capped(self):
        sm = LoopStateMachine(config=ResilienceConfig(
            error_backoff_base=1.0, error_max_backoff=5.0
        ))
        for i in range(1, 20):
            b = sm.get_backoff_time(i)
            assert b <= 5.0

    def test_backoff_jitter(self):
        sm = LoopStateMachine(config=ResilienceConfig(error_backoff_base=1.0))
        # 多次调用同一 retry_count 应略有不同（jitter）
        times = [sm.get_backoff_time(2) for _ in range(10)]
        # 至少有 2 个不同值（因为 jitter）
        assert len(set(round(t, 4) for t in times)) >= 2


# ═══════════════════════════════════════════════════════════
# 场景 6: ResilienceConfig
# ═══════════════════════════════════════════════════════════

class TestResilienceConfig:
    """韧性配置测试"""

    def test_default_config(self):
        config = ResilienceConfig()
        assert config.max_output_tokens_retries == 3
        assert config.ptl_max_retries == 2
        assert config.error_max_retries == 2
        assert config.ptl_compression_target == 0.60
        assert config.model_timeout == 120.0

    def test_custom_config(self):
        config = ResilienceConfig(
            max_output_tokens_retries=5,
            ptl_max_retries=3,
            error_max_retries=1,
        )
        sm = LoopStateMachine(config=config)
        assert sm.config.max_output_tokens_retries == 5


# ═══════════════════════════════════════════════════════════
# 场景 7: 状态机统计
# ═══════════════════════════════════════════════════════════

class TestLoopStateMachineStats:
    """状态机统计测试"""

    def test_stats_tracking(self):
        sm = LoopStateMachine()
        sm.evaluate_response("length")  # 1 retry
        sm.evaluate_response("stop", is_hard_limit=True)  # 1 PTL
        stats = sm.get_stats()
        assert stats["total_retries"] >= 1
        assert stats["total_ptl_retries"] >= 1

    def test_reset_stats(self):
        sm = LoopStateMachine()
        sm.evaluate_response("length")
        sm.reset_session_stats()
        stats = sm.get_stats()
        assert stats["total_retries"] == 0
        assert stats["total_ptl_retries"] == 0


# ═══════════════════════════════════════════════════════════
# 场景 8: LoopState 属性
# ═══════════════════════════════════════════════════════════

class TestLoopState:
    """LoopState 属性测试"""

    def test_should_terminate(self):
        state = LoopState()
        state.termination_reason = TerminationReason.MODEL_ERROR
        assert state.should_terminate

    def test_should_not_terminate(self):
        state = LoopState()
        assert not state.should_terminate

    def test_should_continue(self):
        state = LoopState()
        state.continue_reason = ContinueReason.ERROR_RETRY
        assert state.should_continue
        assert not state.should_terminate

    def test_terminate_takes_precedence(self):
        state = LoopState()
        state.continue_reason = ContinueReason.ERROR_RETRY
        state.termination_reason = TerminationReason.MODEL_ERROR
        # 终止优先
        assert not state.should_continue


# ═══════════════════════════════════════════════════════════
# 场景 9: 人类可读描述
# ═══════════════════════════════════════════════════════════

class TestDescriptions:
    """终止/继续描述测试"""

    def test_all_termination_reasons_have_descriptions(self):
        for reason in TerminationReason:
            assert reason in TERMINATION_DESCRIPTIONS

    def test_all_continue_reasons_have_descriptions(self):
        for reason in ContinueReason:
            assert reason in CONTINUE_DESCRIPTIONS


# ═══════════════════════════════════════════════════════════
# 场景 10: AgentLoop 集成测试
# ═══════════════════════════════════════════════════════════

class TestAgentLoopResilience:
    """AgentLoop 韧性集成测试"""

    def _make_mock_model(self):
        """创建 mock 模型"""
        model = MagicMock()
        model.get_model_name.return_value = "test-model"
        model.get_context_window.return_value = 128000
        model.count_tokens.return_value = 100
        model.supports_feature.return_value = True
        return model

    def test_agent_loop_has_resilience(self):
        """AgentLoop 构造后包含韧性状态机"""
        from agent_loop import AgentLoop
        model = self._make_mock_model()
        loop = AgentLoop(model=model, system_prompt="test", project_root=".")
        assert hasattr(loop, 'resilience')
        assert isinstance(loop.resilience, LoopStateMachine)
        assert hasattr(loop, '_loop_state')

    def test_agent_loop_has_resilience_methods(self):
        """AgentLoop 有韧性相关方法"""
        from agent_loop import AgentLoop
        model = self._make_mock_model()
        loop = AgentLoop(model=model, system_prompt="test", project_root=".")
        assert hasattr(loop, '_call_model_with_resilience')
        assert hasattr(loop, '_try_compact_for_ptl')
        assert callable(loop._call_model_with_resilience)
        assert callable(loop._try_compact_for_ptl)

    def test_resilience_config_in_init(self):
        """韧性配置在初始化时创建"""
        from agent_loop import AgentLoop
        model = self._make_mock_model()
        loop = AgentLoop(model=model, system_prompt="test", project_root=".")
        assert loop.resilience.config.max_output_tokens_retries == 3
        assert loop.resilience.config.ptl_max_retries == 2


# ═══════════════════════════════════════════════════════════
# 运行
# ═══════════════════════════════════════════════════════════

if __name__ == "__main__":
    logging.basicConfig(level=logging.WARNING)
    pytest.main([__file__, "-v", "--tb=short"])
