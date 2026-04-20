#!/usr/bin/env python3
"""
ADDS Agent Loop State — 循环状态机与韧性策略

P1 功能：Agent Loop 韧性增强

核心能力：
- 7 种终止条件（TerminationReason）
- 5 种继续条件（ContinueReason）
- 循环状态机（LoopStateMachine）
- PTL 恢复策略
- max_output_tokens 重试策略
- 错误分类与恢复策略

参考：Claude Code 架构白皮书 — 终止判定（7 种终止 + 4 种继续）
"""

import logging
from dataclasses import dataclass, field
from enum import Enum
from typing import Optional, List

logger = logging.getLogger(__name__)


# ═══════════════════════════════════════════════════════════
# 终止条件枚举
# ═══════════════════════════════════════════════════════════

class TerminationReason(Enum):
    """7 种终止条件

    参考 Claude Code 架构白皮书 §4.2 阶段 4：终止判定
    """

    # 正常终止
    COMPLETED = "completed"                     # 用户主动退出或模型正常完成
    BLOCKING_LIMIT = "blocking_limit"           # Token 超硬限制且恢复无效
    ABORTED_STREAMING = "aborted_streaming"      # 用户中止流式输出（ESC/Ctrl+C）
    MODEL_ERROR = "model_error"                  # 模型调用异常且重试耗尽
    PROMPT_TOO_LONG = "prompt_too_long"          # 413 错误且压缩恢复无效
    IMAGE_ERROR = "image_error"                  # 图片处理错误
    HOOK_PREVENTED = "hook_prevented"            # Stop hook 阻止继续


class ContinueReason(Enum):
    """5 种继续条件

    正常循环 + 4 种特殊恢复路径
    """

    NORMAL = "normal"                            # 正常对话循环
    MAX_OUTPUT_TOKENS = "max_output_tokens"      # 模型输出被截断，需续写
    PROMPT_TOO_LONG = "prompt_too_long"          # Token 超限，压缩后重试
    ERROR_RETRY = "error_retry"                  # 可恢复错误重试
    HOOK_RETRY = "hook_retry"                    # Hook 阻塞后重试


class ErrorCategory(Enum):
    """错误分类

    决定恢复策略：环境错误/模型错误/用户中断/系统错误
    """

    ENVIRONMENT = "environment"   # 环境问题（网络、API Key 等）
    MODEL = "model"               # 模型错误（413、500、超时等）
    USER_ABORT = "user_abort"     # 用户中断
    SYSTEM = "system"             # 系统错误（内存、IO 等）
    UNKNOWN = "unknown"           # 未知错误


# ═══════════════════════════════════════════════════════════
# 恢复策略配置
# ═══════════════════════════════════════════════════════════

@dataclass
class ResilienceConfig:
    """韧性配置

    控制重试次数、超时、退避策略等
    """

    # max_output_tokens 重试
    max_output_tokens_retries: int = 3          # 最多续写 3 次
    max_output_tokens_cooldown: float = 0.5     # 续写冷却时间（秒）

    # PTL 恢复
    ptl_max_retries: int = 2                    # PTL 最多压缩重试 2 次
    ptl_compression_target: float = 0.60        # PTL 压缩目标利用率

    # 通用错误重试
    error_max_retries: int = 2                  # 通用错误最多重试 2 次
    error_backoff_base: float = 1.0             # 指数退避基础时间（秒）
    error_max_backoff: float = 30.0             # 最大退避时间（秒）

    # 模型超时
    model_timeout: float = 120.0                # 单次模型调用超时（秒）

    # 用户中止恢复
    abort_cooldown: float = 1.0                 # 用户中止后冷却时间


# ═══════════════════════════════════════════════════════════
# 循环状态机
# ═══════════════════════════════════════════════════════════

@dataclass
class LoopState:
    """单次模型调用的循环状态

    追踪本轮调用的终止/继续判定
    """

    continue_reason: Optional[ContinueReason] = None
    termination_reason: Optional[TerminationReason] = None

    # 重试计数
    max_output_tokens_count: int = 0
    ptl_retry_count: int = 0
    error_retry_count: int = 0

    # 累积的续写内容（用于 max_output_tokens 恢复）
    continuation_parts: List[str] = field(default_factory=list)

    # 错误信息
    last_error: Optional[str] = None
    error_category: Optional[ErrorCategory] = None

    @property
    def should_terminate(self) -> bool:
        """是否应该终止循环"""
        return self.termination_reason is not None

    @property
    def should_continue(self) -> bool:
        """是否应该继续循环"""
        return self.continue_reason is not None and not self.should_terminate


class LoopStateMachine:
    """Agent Loop 状态机

    管理循环的终止/继续判定逻辑。

    使用方式:
        sm = LoopStateMachine(config=ResilienceConfig())
        state = sm.evaluate_response(finish_reason, error, budget)

        if state.should_terminate:
            # 终止循环
            break
        elif state.should_continue:
            # 继续循环（可能需要压缩/续写）
            handle_continue(state.continue_reason)
    """

    def __init__(self, config: Optional[ResilienceConfig] = None):
        self.config = config or ResilienceConfig()
        self._session_total_retries: int = 0
        self._session_total_ptl: int = 0

    def evaluate_response(
        self,
        finish_reason: str,
        error: Optional[Exception] = None,
        is_hard_limit: bool = False,
        is_user_abort: bool = False,
    ) -> LoopState:
        """评估模型响应，决定终止或继续

        Args:
            finish_reason: 模型返回的结束原因
                - "stop": 正常结束
                - "length": 输出被截断（max_output_tokens）
                - "error": 模型错误
                - "content_filter": 内容过滤
                - "streaming": 流式中
                - "thinking": 思考中
            error: 异常对象（如有）
            is_hard_limit: 是否已达到 Token 硬限制
            is_user_abort: 是否用户主动中止

        Returns:
            LoopState: 循环状态判定
        """
        state = LoopState()

        # 1. 用户中止 → 立即终止
        if is_user_abort:
            state.termination_reason = TerminationReason.ABORTED_STREAMING
            return state

        # 2. Token 硬限制 → 检查 PTL 恢复
        if is_hard_limit:
            if state.ptl_retry_count < self.config.ptl_max_retries:
                state.continue_reason = ContinueReason.PROMPT_TOO_LONG
                state.ptl_retry_count = self._session_total_ptl + 1
                self._session_total_ptl += 1
                logger.info(
                    f"PTL recovery attempt {state.ptl_retry_count}/"
                    f"{self.config.ptl_max_retries}"
                )
            else:
                state.termination_reason = TerminationReason.BLOCKING_LIMIT
                logger.warning("PTL recovery exhausted, blocking limit reached")
            return state

        # 3. 模型错误 → 分类处理
        if error is not None:
            return self._evaluate_error(state, error)

        # 4. finish_reason 判定
        if finish_reason == "stop":
            # 正常完成 → 不需要继续
            state.continue_reason = None
            state.termination_reason = None
            return state

        elif finish_reason == "length":
            # 输出截断 → max_output_tokens 恢复
            if self._session_total_retries < self.config.max_output_tokens_retries:
                state.continue_reason = ContinueReason.MAX_OUTPUT_TOKENS
                state.max_output_tokens_count = self._session_total_retries + 1
                self._session_total_retries += 1
                logger.info(
                    f"max_output_tokens recovery attempt "
                    f"{state.max_output_tokens_count}/"
                    f"{self.config.max_output_tokens_retries}"
                )
            else:
                # 超过重试次数 → 作为正常完成处理
                logger.warning(
                    "max_output_tokens retries exhausted, "
                    "treating as partial completion"
                )
                state.termination_reason = None
            return state

        elif finish_reason == "error":
            # 模型返回错误 → 终止
            state.termination_reason = TerminationReason.MODEL_ERROR
            return state

        elif finish_reason == "content_filter":
            # 内容过滤 → 终止
            state.termination_reason = TerminationReason.MODEL_ERROR
            state.last_error = "Content filtered by model"
            return state

        # 其他情况（streaming/thinking 等中间状态）→ 正常继续
        return state

    def _evaluate_error(self, state: LoopState, error: Exception) -> LoopState:
        """错误分类与恢复策略

        错误分类规则：
        - 环境错误: ConnectionError, TimeoutError, OSError
        - 模型错误: HTTP 413, 429, 500+
        - 用户中止: KeyboardInterrupt
        - 系统错误: MemoryError, 其他
        """
        category = self._classify_error(error)
        state.error_category = category
        state.last_error = str(error)

        if category == ErrorCategory.ENVIRONMENT:
            # 环境错误 → 可重试
            if self._session_total_retries < self.config.error_max_retries:
                state.continue_reason = ContinueReason.ERROR_RETRY
                state.error_retry_count = self._session_total_retries + 1
                self._session_total_retries += 1
                logger.info(
                    f"Environment error retry {state.error_retry_count}/"
                    f"{self.config.error_max_retries}: {error}"
                )
            else:
                state.termination_reason = TerminationReason.MODEL_ERROR
                logger.warning(f"Environment error retries exhausted: {error}")

        elif category == ErrorCategory.MODEL:
            # 检查是否为 PTL (413)
            error_str = str(error).lower()
            if "413" in error_str or "prompt_too_long" in error_str or "context_length" in error_str:
                if self._session_total_ptl < self.config.ptl_max_retries:
                    state.continue_reason = ContinueReason.PROMPT_TOO_LONG
                    state.ptl_retry_count = self._session_total_ptl + 1
                    self._session_total_ptl += 1
                    logger.info(f"PTL detected from model error, retry {state.ptl_retry_count}")
                else:
                    state.termination_reason = TerminationReason.PROMPT_TOO_LONG
                    logger.warning("PTL recovery exhausted")
            elif "429" in error_str or "rate" in error_str:
                # 速率限制 → 可重试
                if self._session_total_retries < self.config.error_max_retries:
                    state.continue_reason = ContinueReason.ERROR_RETRY
                    state.error_retry_count = self._session_total_retries + 1
                    self._session_total_retries += 1
                else:
                    state.termination_reason = TerminationReason.MODEL_ERROR
            else:
                # 其他模型错误 → 终止
                state.termination_reason = TerminationReason.MODEL_ERROR

        elif category == ErrorCategory.USER_ABORT:
            state.termination_reason = TerminationReason.ABORTED_STREAMING

        elif category == ErrorCategory.SYSTEM:
            # 系统错误 → 不重试
            state.termination_reason = TerminationReason.MODEL_ERROR

        else:
            # 未知错误 → 保守终止
            state.termination_reason = TerminationReason.MODEL_ERROR

        return state

    @staticmethod
    def _classify_error(error: Exception) -> ErrorCategory:
        """错误分类

        根据异常类型和消息内容判断错误类别
        """
        if isinstance(error, KeyboardInterrupt):
            return ErrorCategory.USER_ABORT

        if isinstance(error, (ConnectionError, TimeoutError, OSError)):
            return ErrorCategory.ENVIRONMENT

        if isinstance(error, MemoryError):
            return ErrorCategory.SYSTEM

        error_str = str(error).lower()

        # 模型 API 错误
        http_model_errors = ["413", "429", "500", "502", "503", "504"]
        model_keywords = ["api", "model", "token", "context_length", "rate_limit",
                          "prompt_too_long", "content_filter"]
        if any(code in error_str for code in http_model_errors):
            return ErrorCategory.MODEL
        if any(kw in error_str for kw in model_keywords):
            return ErrorCategory.MODEL

        # 网络错误
        network_keywords = ["connection", "timeout", "network", "dns", "resolve"]
        if any(kw in error_str for kw in network_keywords):
            return ErrorCategory.ENVIRONMENT

        return ErrorCategory.UNKNOWN

    def get_backoff_time(self, retry_count: int) -> float:
        """计算指数退避时间

        Args:
            retry_count: 当前重试次数（从 1 开始）

        Returns:
            退避等待时间（秒）
        """
        import math
        backoff = self.config.error_backoff_base * (2 ** (retry_count - 1))
        # 加 jitter
        jitter = backoff * 0.1
        backoff += jitter
        return min(backoff, self.config.error_max_backoff)

    def get_stats(self) -> dict:
        """获取状态机统计信息"""
        return {
            "total_retries": self._session_total_retries,
            "total_ptl_retries": self._session_total_ptl,
        }

    def reset_session_stats(self) -> None:
        """重置会话统计"""
        self._session_total_retries = 0
        self._session_total_ptl = 0


# ═══════════════════════════════════════════════════════════
# 终止原因的人类可读描述
# ═══════════════════════════════════════════════════════════

TERMINATION_DESCRIPTIONS = {
    TerminationReason.COMPLETED: "✅ 对话正常结束",
    TerminationReason.BLOCKING_LIMIT: "⛔ Token 预算耗尽且恢复无效",
    TerminationReason.ABORTED_STREAMING: "🛑 用户中止了流式输出",
    TerminationReason.MODEL_ERROR: "❌ 模型调用异常且重试耗尽",
    TerminationReason.PROMPT_TOO_LONG: "📏 上下文超长且压缩恢复无效",
    TerminationReason.IMAGE_ERROR: "🖼️ 图片处理错误",
    TerminationReason.HOOK_PREVENTED: "🚫 Hook 阻止继续执行",
}

CONTINUE_DESCRIPTIONS = {
    ContinueReason.NORMAL: "正常对话循环",
    ContinueReason.MAX_OUTPUT_TOKENS: "模型输出被截断，正在续写...",
    ContinueReason.PROMPT_TOO_LONG: "上下文超限，正在压缩后重试...",
    ContinueReason.ERROR_RETRY: "可恢复错误，正在重试...",
    ContinueReason.HOOK_RETRY: "Hook 阻塞后重试...",
}


# ═══════════════════════════════════════════════════════════
# 单元测试
# ═══════════════════════════════════════════════════════════

if __name__ == "__main__":
    from log_config import configure_standalone_logging
    configure_standalone_logging()

    # 测试状态机
    sm = LoopStateMachine()

    # 场景 1: 正常完成
    state = sm.evaluate_response("stop")
    assert not state.should_terminate
    assert not state.should_continue
    print("✅ 正常完成")

    # 场景 2: max_output_tokens 恢复
    state = sm.evaluate_response("length")
    assert state.should_continue
    assert state.continue_reason == ContinueReason.MAX_OUTPUT_TOKENS
    print(f"✅ max_output_tokens 恢复 (attempt {state.max_output_tokens_count})")

    # 场景 3: PTL 恢复
    state = sm.evaluate_response("stop", is_hard_limit=True)
    assert state.should_continue
    assert state.continue_reason == ContinueReason.PROMPT_TOO_LONG
    print(f"✅ PTL 恢复 (attempt {state.ptl_retry_count})")

    # 场景 4: 环境错误重试
    sm.reset_session_stats()
    state = sm.evaluate_response("stop", error=ConnectionError("Network unreachable"))
    assert state.should_continue
    assert state.continue_reason == ContinueReason.ERROR_RETRY
    print(f"✅ 环境错误重试 (attempt {state.error_retry_count})")

    # 场景 5: 413 PTL 恢复
    sm.reset_session_stats()
    state = sm.evaluate_response("stop", error=Exception("HTTP 413: prompt_too_long"))
    assert state.should_continue
    assert state.continue_reason == ContinueReason.PROMPT_TOO_LONG
    print(f"✅ 413 PTL 恢复 (attempt {state.ptl_retry_count})")

    # 场景 6: 用户中止
    state = sm.evaluate_response("stop", is_user_abort=True)
    assert state.should_terminate
    assert state.termination_reason == TerminationReason.ABORTED_STREAMING
    print("✅ 用户中止")

    # 场景 7: 重试耗尽
    sm.reset_session_stats()
    for i in range(3):
        state = sm.evaluate_response("length")
        assert state.should_continue
    # 第 4 次不再继续
    state = sm.evaluate_response("length")
    assert not state.should_continue
    print(f"✅ max_output_tokens 重试耗尽")

    # 场景 8: 退避时间
    sm2 = LoopStateMachine()
    for i in range(1, 4):
        t = sm2.get_backoff_time(i)
        print(f"  退避 {i}: {t:.2f}s")

    print("\n✅ 所有测试通过")
