#!/usr/bin/env python3
"""
ADDS Agent Core — 共享核心逻辑层

CLI 和 TUI 统一使用此模块，界面只是壳。
核心能力：
- Agent Loop（模型→工具→模型循环）
- 韧性增强（续写恢复、PTL 压缩恢复、错误重试）
- Token 预算管理 + 两层压缩
- Session 管理 + 归档
- 记忆管理 + 进化
- 权限管理
- 技能管理
- 工具执行

所有 UI 反馈通过回调接口（AgentCallbacks）实现，
CLI 和 TUI 各自实现回调即可获得完整功能。
"""

from __future__ import annotations

import asyncio
import logging
import subprocess
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Tuple

from model.base import ModelInterface, ModelResponse
from token_budget import TokenBudget, estimate_tokens, load_budget_config
from session_manager import SessionManager
from context_compactor import ContextCompactor
from summary_decision_engine import SummaryStrategy
from memory_manager import MemoryManager
from permission_manager import PermissionManager, PermissionDecision, PermissionLevel
from loop_state import (
    LoopStateMachine, LoopState, ResilienceConfig,
    TerminationReason, ContinueReason, ErrorCategory,
    TERMINATION_DESCRIPTIONS, CONTINUE_DESCRIPTIONS,
)

logger = logging.getLogger(__name__)


# ═══════════════════════════════════════════════════════════
# 内置角色
# ═══════════════════════════════════════════════════════════

BUILTIN_ROLES = {
    "pm":         "你是一个项目经理，等待接受我的任务",
    "architect":  "你是一个架构师，专注于技术架构设计和技术选型",
    "developer":  "你是一个开发者，专注于功能实现和代码编写",
    "tester":     "你是一个测试工程师，专注于测试验证和质量保障",
    "reviewer":   "你是一个代码审查员，专注于代码质量、安全和最佳实践",
}


# ═══════════════════════════════════════════════════════════
# 回调接口 — UI 层实现
# ═══════════════════════════════════════════════════════════

@dataclass
class AgentCallbacks:
    """UI 回调接口 — CLI/TUI 各自实现

    所有回调可选（None 时跳过），确保核心逻辑不依赖任何 UI。
    """
    # 流式文本片段
    on_chunk: Optional[Callable[[str], None]] = None
    # 思考过程（text, is_first）
    on_thinking: Optional[Callable[[str, bool], None]] = None
    # 工具调用（tool_name, args）
    on_tool_call: Optional[Callable[[str, dict], None]] = None
    # Agent Loop 状态变化（thinking/streaming/tool_call/executing/waiting/idle）
    on_status: Optional[Callable[[str], None]] = None
    # 完整回复完成（full_text）
    on_done: Optional[Callable[[str], None]] = None
    # 错误消息（error_text）
    on_error: Optional[Callable[[str], None]] = None
    # 权限确认请求 → 返回 True(允许) / False(拒绝)
    on_permission_ask: Optional[Callable[[PermissionDecision], bool]] = None
    # 警告消息（warning_text）
    on_warning: Optional[Callable[[str], None]] = None
    # PTL 压缩通知
    on_compact: Optional[Callable[[str, int], None]] = None  # (strategy, saved_tokens)
    # 续写通知
    on_continuation: Optional[Callable[[int], None]] = None  # (attempt_number)


# ═══════════════════════════════════════════════════════════
# Agent Core — 核心逻辑
# ═══════════════════════════════════════════════════════════

class AgentCore:
    """
    Agent 核心逻辑 — CLI 和 TUI 共享

    所有 UI 交互通过 AgentCallbacks 回调实现，
    核心逻辑完全不依赖具体的渲染方式。
    """

    def __init__(
        self,
        model: ModelInterface,
        project_root: str = ".",
        agent_role: str = "pm",
        feature: str = "",
        permission_mode: str = "default",
        callbacks: Optional[AgentCallbacks] = None,
    ):
        self.model = model
        self.project_root = Path(project_root)
        self.agent_role = agent_role
        self.feature = feature
        self.callbacks = callbacks or AgentCallbacks()

        # ── 核心子系统 ──────────────────────────────
        ctx_window = model.get_context_window()
        budget_config = load_budget_config(project_root)
        sessions_dir = str(self.project_root / ".ai" / "sessions")

        # P0-2: Token 预算 + Session + 压缩
        self.budget = TokenBudget(context_window=ctx_window, config=budget_config)
        self.session_mgr = SessionManager(sessions_dir=sessions_dir)
        self.compactor = ContextCompactor(self.budget, self.session_mgr)

        # P0-3: 记忆
        self.memory_mgr = MemoryManager(
            sessions_dir=sessions_dir,
            project_root=project_root,
        )

        # P0-4: 权限
        self.permission = PermissionManager(
            project_root=project_root, mode=permission_mode,
        )

        # P1: 韧性状态机
        self.resilience = LoopStateMachine(config=ResilienceConfig())

        # P1: 技能管理
        from skill_manager import SkillManager
        self.skill_mgr = SkillManager(project_root=project_root)

        # ── 会话状态 ─────────────────────────────────
        self.messages: List[Dict[str, Any]] = []
        self.system_prompt: str = BUILTIN_ROLES.get(agent_role, f"你是一个 {agent_role} 角色的 AI 助手")
        self.turn_count: int = 0
        self.streaming: bool = False

        # 注入 Level 0 技能索引
        skill_section = self.skill_mgr.build_level0_section()
        if skill_section:
            self.system_prompt += "\n\n" + skill_section

        # 模型锁（防止并发调用）
        self._model_lock = asyncio.Lock()

    # ── 初始化 ──────────────────────────────────────────

    def init_session(self) -> None:
        """初始化 Session 和 Token 预算（启动时调用）"""
        ctx_window = self.model.get_context_window()
        session_id = self.session_mgr.create_session(
            agent=self.agent_role,
            feature=self.feature,
        )

        # 注入上一个 session 的摘要
        prev_summary = self.session_mgr.get_prev_session_summary()
        if prev_summary:
            self.system_prompt += f"\n\n## 上一次对话摘要\n{prev_summary[:2000]}"

        # 注入固定记忆
        memory_injection = self.memory_mgr.build_memory_injection(role=self.agent_role)
        if memory_injection:
            self.system_prompt += f"\n\n## 项目经验记忆\n{memory_injection}"

        # Token 预算初始化
        system_tokens = estimate_tokens(self.system_prompt)
        self.budget.allocate(system_prompt=system_tokens)
        logger.info("Session initialized: %s | ctx=%d | system_tokens=%d",
                     session_id, ctx_window, system_tokens)

    # ── 核心：Agent Loop ────────────────────────────────

    async def send_message(self, user_text: str,
                           callbacks: Optional[AgentCallbacks] = None) -> Optional[str]:
        """
        Agent Loop 主入口 — 模型→工具→模型循环

        Args:
            user_text: 用户输入
            callbacks: 可覆盖默认回调

        Returns:
            最终助手回复文本
        """
        cb = callbacks or self.callbacks

        if not self.model:
            if cb.on_error:
                cb.on_error("❌ 模型未初始化")
            return None

        # 追加用户消息
        self.messages.append({"role": "user", "content": user_text})
        self.turn_count += 1
        self.resilience.reset_session_stats()

        # 记录到 Session
        self.session_mgr.append_message("user", user_text)

        # Token 预算检查
        self.budget.track(f"turn_{self.turn_count}_user", estimate_tokens(user_text))

        # ── Agent Loop ──────────────────────────────
        full_response_parts: List[str] = []
        max_tool_rounds = 8

        self.streaming = True
        try:
            for round_num in range(max_tool_rounds + 1):
                # 检查 Token 预算 — Layer1 压缩
                if self.budget.utilization > 0.50:
                    self._compact_layer1(cb)

                # 动态构建消息
                messages = self._build_messages()

                logger.info("AgentLoop round %d/%d | msgs=%d | budget=%.1f%%",
                            round_num + 1, max_tool_rounds,
                            len(messages), self.budget.utilization * 100)

                # 单轮模型调用（韧性增强）
                round_result = await self._call_model_with_resilience(
                    messages, cb, round_num,
                )

                # 有文本回复 → 收集并退出循环
                if round_result.text:
                    full_response_parts.append(round_result.text)
                    break

                # 纯工具调用 → 执行后继续
                if round_result.tool_calls:
                    logger.info("AgentLoop round %d: %d 工具调用",
                                round_num + 1, len(round_result.tool_calls))

                    if cb.on_status:
                        cb.on_status("executing")

                    # 将模型决策加入消息历史
                    tool_names = [t[0] or "unknown" for t in round_result.tool_calls]
                    assistant_msg = f"调用工具: {', '.join(tool_names)}"
                    self.messages.append({"role": "assistant", "content": assistant_msg})
                    self.session_mgr.append_message("assistant", assistant_msg)

                    # 执行每个工具
                    for tname, targs in round_result.tool_calls:
                        # ── 权限检查 ──
                        decision = self.permission.check(tname, str(targs))
                        if decision.needs_confirmation:
                            allowed = await self._ask_permission(decision, cb)
                            if not allowed:
                                result = f"🚫 用户拒绝了工具调用: {tname}"
                                if cb.on_error:
                                    cb.on_error(result)
                            else:
                                result = await self._execute_tool(tname, targs)
                        elif decision.is_denied:
                            result = f"🚫 权限拒绝: {decision.reason}"
                            if cb.on_error:
                                cb.on_error(result)
                        else:
                            result = await self._execute_tool(tname, targs)

                        self.messages.append({"role": "tool_result", "content": result})
                        self.session_mgr.append_message("tool_result", result)

                        # 工具输出保存到 .log
                        if len(result) > 2000:
                            summary = result[:500] + "..."
                            self.session_mgr.save_tool_output(
                                result, summary=summary, strategy="tool_filter"
                            )
                        logger.debug("Tool Result | %s => %d chars", tname, len(result))

                    # Token 预算更新
                    for tname, targs in round_result.tool_calls:
                        result_msg = next(
                            (m for m in self.messages if m["role"] == "tool_result"),
                            {}
                        )
                        if result_msg:
                            self.budget.reserve(
                                f"tool_{tname}", estimate_tokens(result_msg.get("content", ""))
                            )

                    continue  # 下一轮

                # 无文本也无工具 → 空回复
                logger.warning("AgentLoop round %d: 无文本无工具调用", round_num + 1)
                break

        except Exception as e:
            logger.error("AgentLoop failed: %s", e, exc_info=True)
            if cb.on_error:
                cb.on_error(f"❌ 调用失败: {e}")
        finally:
            self.streaming = False
            if cb.on_status:
                cb.on_status("idle")

        # 合并完整回复
        full_text = "".join(full_response_parts)

        if full_text:
            self.messages.append({"role": "assistant", "content": full_text})
            self.session_mgr.append_message(
                "assistant", full_text,
                strategy="llm_analyze", priority="high",
            )
            self.budget.track(
                f"turn_{self.turn_count}_assistant", estimate_tokens(full_text)
            )

            # Token 预算警告
            warning = self.compactor.get_warning()
            if warning and cb.on_warning:
                cb.on_warning(warning)

            # 检查硬限制
            if self.budget.is_hard_limit():
                self._try_compact_for_ptl(cb)

        if cb.on_done:
            cb.on_done(full_text)

        return full_text

    # ── 韧性增强模型调用 ────────────────────────────────

    @dataclass
    class _RoundResult:
        """单轮模型调用结果"""
        text: str = ""
        thinking: str = ""
        tool_calls: List[Tuple[str, dict]] = field(default_factory=list)
        finish_reason: str = "stop"

    async def _call_model_with_resilience(
        self,
        messages: List[Dict],
        cb: AgentCallbacks,
        round_num: int = 0,
    ) -> "AgentCore._RoundResult":
        """
        韧性增强的单轮模型调用

        支持：max_output_tokens 续写、PTL 恢复、错误重试、用户中止
        """
        full_response_parts: List[str] = []
        is_continuation = False

        while True:
            result = self._RoundResult()
            thinking_parts: List[str] = []
            tool_calls: List[Tuple[str, dict]] = []
            _thinking_shown = False
            finish_reason = "stop"
            error_occurred = None

            try:
                # 续写模式：添加续写提示
                call_messages = messages
                if is_continuation and full_response_parts:
                    call_messages = list(messages) + [
                        {"role": "user", "content": "（接上文，请继续完成被截断的回复）"}
                    ]

                async with self._model_lock:
                    async for resp in self.model.chat(
                        call_messages,
                        system_prompt=self.system_prompt or None,
                        stream=True,
                    ):
                        # ── Debug 日志 ──
                        logger.debug(
                            "LLM | round=%d | finish=%r | content=%d | thinking=%d | tools=%d",
                            round_num + 1, resp.finish_reason,
                            len(resp.content or ""), len(resp.thinking or ""),
                            len(resp.tool_calls or []),
                        )

                        if resp.progress_hints:
                            for hint in resp.progress_hints:
                                logger.debug("  progress | %s", hint)

                        # ── 错误 ──
                        if resp.finish_reason == "error":
                            if cb.on_error:
                                cb.on_error(f"❌ 模型错误: {resp.content}")
                            result.finish_reason = "error"
                            return result

                        # ── 思考过程 ──
                        if resp.thinking and resp.finish_reason == "thinking":
                            thinking_parts.append(resp.thinking)
                            if not _thinking_shown:
                                _thinking_shown = True
                                if cb.on_thinking:
                                    cb.on_thinking(resp.thinking, True)
                                if cb.on_status:
                                    cb.on_status("thinking")
                            else:
                                if cb.on_thinking:
                                    cb.on_thinking(resp.thinking, False)

                        # ── 工具调用 ──
                        if resp.tool_calls:
                            for tc in resp.tool_calls:
                                tname = tc.get("name") if isinstance(tc, dict) else getattr(tc, "name", None)
                                targs = tc.get("arguments") if isinstance(tc, dict) else getattr(tc, "arguments", {})
                                tool_calls.append((tname, targs))
                                logger.debug("LLM >> tool_call | %s", tname)
                                if cb.on_tool_call:
                                    cb.on_tool_call(tname, targs)
                                if cb.on_status:
                                    cb.on_status("tool_call")

                        # ── 流式文本 ──
                        if resp.content and resp.finish_reason == "streaming":
                            result.text += resp.content
                            if cb.on_chunk:
                                cb.on_chunk(resp.content)
                            if cb.on_status:
                                cb.on_status("streaming")

                        # ── 非流式 stop ──
                        elif resp.finish_reason == "stop" and resp.content:
                            result.text += resp.content
                            if cb.on_chunk:
                                cb.on_chunk(resp.content)

                        # ── length 截断 ──
                        if resp.finish_reason == "length":
                            finish_reason = "length"
                            if resp.content:
                                result.text += resp.content
                                if cb.on_chunk:
                                    cb.on_chunk(resp.content)

            except KeyboardInterrupt:
                loop_state = self.resilience.evaluate_response(
                    finish_reason="stop", is_user_abort=True
                )
                if cb.on_warning:
                    cb.on_warning("⚠️ 流式输出已中止")
                break

            except Exception as e:
                error_occurred = e
                loop_state = self.resilience.evaluate_response(
                    finish_reason="stop", error=e
                )

                if loop_state.should_continue and loop_state.continue_reason == ContinueReason.ERROR_RETRY:
                    backoff = self.resilience.get_backoff_time(loop_state.error_retry_count)
                    logger.info("Error retry %d in %.1fs: %s",
                                loop_state.error_retry_count, backoff, e)
                    if cb.on_warning:
                        cb.on_warning(f"⚠️ 可恢复错误，{backoff:.0f}s 后重试: {e}")
                    await asyncio.sleep(backoff)
                    continue

                if loop_state.should_continue and loop_state.continue_reason == ContinueReason.PROMPT_TOO_LONG:
                    logger.info("PTL detected from error, attempting compression")
                    if self._try_compact_for_ptl(cb):
                        continue

                if cb.on_error:
                    cb.on_error(f"❌ 模型调用失败: {e}")
                result.finish_reason = "error"
                return result

            # ── 续写恢复（max_output_tokens）──────────
            if finish_reason == "length":
                loop_state = self.resilience.evaluate_response("length")
                if loop_state.should_continue:
                    full_response_parts.append(result.text)
                    is_continuation = True
                    if cb.on_continuation:
                        cb.on_continuation(loop_state.max_output_tokens_count)
                    logger.info("Continuation attempt %d", loop_state.max_output_tokens_count)
                    continue
                else:
                    # 重试耗尽，作为部分完成
                    full_response_parts.append(result.text)
                    if cb.on_warning:
                        cb.on_warning("⚠️ 输出截断，续写重试已耗尽")

            # 正常完成
            if result.text and full_response_parts:
                result.text = "".join(full_response_parts) + result.text
            elif full_response_parts:
                result.text = "".join(full_response_parts) + result.text

            result.thinking = "".join(thinking_parts)
            result.tool_calls = tool_calls
            result.finish_reason = finish_reason
            return result

        # 中止退出
        result.text = "".join(full_response_parts)
        result.thinking = "".join(thinking_parts)
        result.tool_calls = tool_calls
        return result

    # ── 工具执行 ────────────────────────────────────────

    async def _execute_tool(self, tool_name: str, args: dict) -> str:
        """执行工具调用"""
        if not tool_name:
            return "❌ 工具名为空"

        tool_name = tool_name.lower().strip()
        logger.info("Execute tool: %s | args=%s", tool_name, list(args.keys()) if args else [])

        try:
            if tool_name in ("read", "read_file"):
                return self._tool_read(args)
            elif tool_name in ("glob", "search", "search_file", "find"):
                return self._tool_glob(args)
            elif tool_name in ("grep", "search_content", "rg"):
                return self._tool_grep(args)
            elif tool_name in ("write", "write_file"):
                return self._tool_write(args)
            elif tool_name in ("shell", "bash", "command", "exec"):
                return await self._tool_shell(args)
            else:
                return f"⚠️ 工具 '{tool_name}' 暂未实现\n可用: read, glob, grep, write, shell"

        except Exception as e:
            logger.error("Tool error: %s | %s", tool_name, e)
            return f"❌ 工具执行异常: {e}"

    def _tool_read(self, args: dict) -> str:
        path = args.get("file_path") or args.get("path") or args.get("filename", "")
        if not path:
            return "❌ read: 缺少 file_path"
        p = self._resolve_path(path)
        if not p.exists():
            return f"❌ 文件不存在: {p}"
        try:
            content = p.read_text(encoding="utf-8", errors="replace")
            max_chars = 8000
            if len(content) > max_chars:
                content = content[:max_chars] + f"\n... (截断，共 {len(content)} 字符)"
            return content
        except Exception as e:
            return f"❌ 读取失败: {e}"

    def _tool_glob(self, args: dict) -> str:
        pattern = args.get("pattern") or args.get("glob") or args.get("query", "*")
        directory = args.get("directory") or args.get("path") or str(self.project_root)
        directory = self._resolve_path(directory)
        try:
            matches = list(directory.glob(pattern))[:50]
            if not matches:
                return f"无匹配: pattern={pattern}"
            return "\n".join(str(m.relative_to(self.project_root)) for m in matches)
        except Exception as e:
            return f"❌ 搜索失败: {e}"

    def _tool_grep(self, args: dict) -> str:
        pattern = args.get("pattern") or args.get("query", "")
        path = args.get("path") or str(self.project_root)
        if not pattern:
            return "❌ grep: 缺少 pattern"
        try:
            result = subprocess.run(
                ["grep", "-rn", "--include=*.py", "--include=*.md",
                 "--include=*.yaml", "--include=*.json", pattern, path],
                capture_output=True, text=True, timeout=10,
            )
            output = result.stdout[:5000]
            if not output:
                return f"未找到匹配: pattern={pattern}"
            return output
        except subprocess.TimeoutExpired:
            return "❌ 搜索超时"
        except Exception as e:
            return f"❌ 搜索失败: {e}"

    def _tool_write(self, args: dict) -> str:
        path = args.get("file_path") or args.get("path", "")
        content = args.get("content", "")
        if not path:
            return "❌ write: 缺少 file_path"
        p = self._resolve_path(path)
        try:
            p.parent.mkdir(parents=True, exist_ok=True)
            p.write_text(content, encoding="utf-8")
            return f"✅ 已写入: {p} ({len(content)} 字符)"
        except Exception as e:
            return f"❌ 写入失败: {e}"

    async def _tool_shell(self, args: dict) -> str:
        cmd = args.get("command") or args.get("cmd", "")
        if not cmd:
            return "❌ shell: 缺少 command"
        try:
            result = subprocess.run(
                cmd, shell=True, capture_output=True, text=True,
                timeout=30, cwd=str(self.project_root),
            )
            output = result.stdout[:5000]
            if result.returncode != 0:
                output += f"\n❌ Exit code: {result.returncode}\n{result.stderr[:2000]}"
            return output or "(无输出)"
        except subprocess.TimeoutExpired:
            return "❌ 命令超时（30s）"
        except Exception as e:
            return f"❌ 执行失败: {e}"

    def _resolve_path(self, path_str: str) -> Path:
        p = Path(path_str)
        if not p.is_absolute():
            p = self.project_root / p
        return p.resolve()

    # ── 权限确认 ────────────────────────────────────────

    async def _ask_permission(self, decision: PermissionDecision,
                              cb: AgentCallbacks) -> bool:
        """通过回调请求用户确认权限"""
        if cb.on_permission_ask:
            return cb.on_permission_ask(decision)
        # 无回调时默认拒绝
        logger.warning("Permission ask without callback, denying: %s", decision)
        return False

    # ── 上下文压缩 ──────────────────────────────────────

    def _compact_layer1(self, cb: AgentCallbacks) -> None:
        """Layer1 实时压缩（工具输出截断）"""
        compressed, results = self.compactor.layer1_compress_batch(self.messages)
        if results:
            self.messages = compressed
            saved = sum(r.saved_tokens for r in results if hasattr(r, 'saved_tokens'))
            if saved > 0 and cb.on_compact:
                cb.on_compact("layer1", saved)

    def _try_compact_for_ptl(self, cb: AgentCallbacks) -> bool:
        """PTL 恢复策略：Layer1 压缩 → Layer2 归档 → 新 Session"""
        # Layer1: 压缩工具输出
        compressed, results = self.compactor.layer1_compress_batch(self.messages)
        if results:
            self.messages = compressed
            saved = sum(r.saved_tokens for r in results if hasattr(r, 'saved_tokens'))
            if saved > 0:
                if cb.on_compact:
                    cb.on_compact("layer1_ptl", saved)
                logger.info("PTL: Layer1 saved %d tokens", saved)
                return True

        # Layer2: 归档
        result = self.compactor.layer2_archive(model_interface=self.model)
        if result:
            if cb.on_compact:
                cb.on_compact("layer2", 0)
            logger.info("PTL: Layer2 archive triggered")
            # 清空当前对话历史，开始新 session
            self.messages.clear()
            self.turn_count = 0
            self.budget.reset()
            return True

        if cb.on_warning:
            cb.on_warning("⛔ Token 硬限制且压缩恢复无效")
        return False

    def _build_messages(self) -> List[Dict]:
        """构建模型消息列表"""
        return [
            {"role": m["role"], "content": m["content"]}
            for m in self.messages
            if m["role"] in ("user", "assistant", "tool_result")
        ]

    # ── Session 归档 ────────────────────────────────────

    def archive_session(self, summary: str = "") -> Optional[str]:
        """归档当前 Session → .mem"""
        if not summary and self.messages:
            # 简单自动摘要：取最后一条助手消息
            last_assistant = next(
                (m["content"][:500] for m in reversed(self.messages)
                 if m["role"] == "assistant"), ""
            )
            summary = f"### 对话摘要\n- 角色: {self.agent_role}\n- 轮数: {self.turn_count}\n{last_assistant}"

        try:
            mem_path = self.session_mgr.archive_session(summary=summary)
            logger.info("Session archived: %s", mem_path)

            # 记忆进化评估
            self._evaluate_memory_evolution()
            return mem_path
        except Exception as e:
            logger.error("Archive failed: %s", e)
            return None

    def _evaluate_memory_evolution(self) -> None:
        """记忆进化评估"""
        try:
            prev_summary = self.session_mgr.get_prev_session_summary() or ""
            if prev_summary:
                evaluations = self.memory_mgr.evaluate_and_upgrade(
                    mem_content=prev_summary, role=self.agent_role,
                )
                for ev in evaluations:
                    if ev.should_upgrade:
                        logger.info("Memory upgraded: [%s] %s (confidence=%.2f)",
                                    ev.category, ev.content[:40], ev.confidence)
                # 添加记忆索引
                from datetime import datetime
                self.memory_mgr.add_index_entry(
                    time=datetime.now().strftime("%m-%d %H:%M"),
                    file=f"session_archive",
                    summary=f"Session 归档 (agent={self.agent_role})",
                    priority="高" if self.turn_count > 5 else "中",
                )
        except Exception as e:
            logger.warning("Memory evolution failed: %s", e)

    # ── 状态查询 ────────────────────────────────────────

    def get_stats(self) -> Dict[str, Any]:
        """获取 Agent 状态统计"""
        return {
            "role": self.agent_role,
            "turn_count": self.turn_count,
            "message_count": len(self.messages),
            "token_used": self.budget.used,
            "token_budget": self.budget.context_window,
            "utilization": f"{self.budget.utilization:.1%}",
            "budget_action": self.budget.recommend_action(),
            "permission_mode": self.permission.current_mode,
            "resilience_stats": self.resilience.get_stats(),
        }

    def clear_messages(self) -> None:
        """清空对话历史"""
        self.messages.clear()
        self.turn_count = 0
        self.budget._history = 0
        self.budget._tool_results = 0
