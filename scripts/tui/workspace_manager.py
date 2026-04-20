"""
WorkspaceManager — Agent 工作区管理器

负责：创建/切换/关闭 Workspace，持久化 .mem 文件，
      与 P0-2 SessionManager 和 P0-3 MemoryManager 集成，
      实现 Agent Loop（模型→工具→模型循环）
"""

from __future__ import annotations

import asyncio
import logging
import subprocess
from pathlib import Path
from typing import Optional

from tui.state import AppState, WorkspaceState, WorkspaceStatus

logger = logging.getLogger(__name__)

# 内置角色提示词（与 adds.py 保持一致）
BUILTIN_ROLES = {
    "pm":         "你是一个项目经理，等待接受我的任务",
    "architect":  "你是一个架构师，专注于技术架构设计和技术选型",
    "developer":  "你是一个开发者，专注于功能实现和代码编写",
    "tester":     "你是一个测试工程师，专注于测试验证和质量保障",
    "reviewer":   "你是一个代码审查员，专注于代码质量、安全和最佳实践",
}


class WorkspaceManager:
    """管理所有 Agent 工作区的生命周期"""

    def __init__(self, app_state: AppState, project_root: str = ".") -> None:
        self.state = app_state
        self.project_root = Path(project_root)
        self._model = None          # 共享模型实例（由 App 注入）
        self._model_lock = asyncio.Lock()

    def set_model(self, model) -> None:
        """注入共享模型实例"""
        self._model = model
        if model:
            ctx = model.get_context_window()
            self.state.context_window = ctx

    def create_workspace(self, agent_role: str, task_context: str = "") -> WorkspaceState:
        """创建新的 Agent 工作区"""
        ctx_window = self._model.get_context_window() if self._model else 128000
        ws = self.state.create_workspace(
            agent_role=agent_role,
            task_context=task_context,
            token_budget=ctx_window,
        )
        logger.info(f"Workspace created: {ws.workspace_id} ({agent_role})")
        return ws

    def switch_workspace(self, workspace_id: str) -> bool:
        """切换到指定工作区"""
        ok = self.state.switch_to(workspace_id)
        if ok:
            logger.debug(f"Switched to workspace: {workspace_id}")
        return ok

    def close_workspace(self, workspace_id: str) -> bool:
        """关闭工作区（归档 .mem）"""
        ws = self.state.workspaces.get(workspace_id)
        if not ws:
            return False
        ws.status = WorkspaceStatus.COMPLETED
        # TODO: 触发 P0-2 Layer2 归档 + P0-3 记忆进化
        ok = self.state.close_workspace(workspace_id)
        logger.info(f"Workspace closed: {workspace_id}")
        return ok

    def get_system_prompt(self, agent_role: str) -> str:
        """获取角色对应的系统提示词"""
        return BUILTIN_ROLES.get(agent_role, f"你是一个 {agent_role} 角色的 AI 助手")

    # ── Agent Loop ───────────────────────────────────────────────

    async def send_message(self, workspace_id: str, user_text: str,
                           on_chunk=None, on_done=None,
                           on_thinking=None, on_tool_call=None,
                           on_status=None) -> Optional[str]:
        """
        向指定工作区发送消息 — Agent Loop（模型→工具执行→模型循环）

        回调接口：
        on_chunk(chunk: str)     — 每个流式文本片段回调
        on_done(full: str)       — 完成回调（传入最终完整回复）
        on_thinking(text: str, has_content: bool) — 思考过程回调
        on_tool_call(tool_name: str, args: dict) — 工具调用回调
        on_status(status: str)   — Agent Loop 状态变化（thinking/tool_call/executing/waiting）
        """
        ws = self.state.workspaces.get(workspace_id)
        if not ws:
            return None
        if not self._model:
            err = ws.add_message("system", "❌ 模型未初始化，请重启并选择模型")
            return None

        # 添加用户消息到状态
        ws.add_message("user", user_text)

        system_prompt = self.get_system_prompt(ws.agent_role)
        full_response_parts: list[str] = []
        max_rounds = 8  # 防止无限循环

        ws.streaming = True
        try:
            for round_num in range(max_rounds + 1):
                # 动态构建消息列表（每轮更新，包含工具结果）
                messages = self._build_messages(ws)
                logger.info("AgentLoop round %d/%d | msgs=%d | est_tokens=%d",
                            round_num + 1, max_rounds,
                            len(messages),
                            sum(len(m["content"]) for m in messages) // 4)

                round_response, round_thinking, round_tools = await self._call_model(
                    ws, messages, system_prompt,
                    on_chunk=on_chunk,
                    on_thinking=on_thinking,
                    on_tool_call=on_tool_call,
                    on_status=on_status,
                    round_num=round_num,
                )

                # ── 有文本回复 → 收集并退出循环 ─────────────
                if round_response:
                    full_response_parts.append(round_response)
                    break

                # ── 纯工具调用（无文本）→ 执行后继续 ─────────
                if round_tools:
                    logger.info("AgentLoop round %d: 执行 %d 个工具",
                                round_num + 1, len(round_tools))

                    # 通知 UI 进入执行状态
                    if on_status:
                        on_status("executing")

                    # 将模型的工具调用意图加入消息历史
                    tool_names = [t[0] or "unknown" for t in round_tools]
                    assistant_msg = (
                        f"调用工具: {', '.join(tool_names)}"
                    )
                    ws.add_message("assistant", assistant_msg)

                    # 执行每个工具
                    for tname, targs in round_tools:
                        result = await self._execute_tool(tname, targs, workspace_id)
                        ws.add_message("tool_result", result)
                        logger.info("Tool Result | %s => %d chars", tname, len(result))

                    # 继续下一轮（模型将看到工具结果）
                    continue

                # ── 无文本也无工具调用 → 空回复，退出 ────────
                logger.warning("AgentLoop round %d: 模型无文本无工具调用，退出", round_num + 1)
                break

        except Exception as e:
            logger.error(f"AgentLoop failed: {e}", exc_info=True)
            err_msg = f"❌ 调用失败: {e}"
            ws.add_message("system", err_msg)
            if on_chunk:
                on_chunk(err_msg)
        finally:
            ws.streaming = False
            if on_status:
                on_status("idle")

        full_text = "".join(full_response_parts)
        if full_text:
            ws.add_message("assistant", full_text)
            ws.token_used += len(user_text) // 4 + len(full_text) // 4

        if on_done:
            on_done(full_text)

        return full_text

    async def _call_model(self, ws, messages, system_prompt,
                          on_chunk=None, on_thinking=None,
                          on_tool_call=None, on_status=None,
                          round_num: int = 0):
        """
        单轮模型调用 — 收集完整响应（文本 + thinking + tool_calls）

        Returns:
            (response_text, thinking_text, tool_calls_list)
        """
        full_response: list[str] = []
        thinking_parts: list[str] = []
        tool_calls: list[tuple] = []
        _has_shown_thinking = False

        async with self._model_lock:
            async for resp in self._model.chat(
                messages,
                system_prompt=system_prompt,
                stream=True,
            ):
                # ── Debug 日志 ─────────────────────────────────
                logger.debug(
                    "LLM Resp | round=%d | finish_reason=%r | content_len=%d | thinking_len=%d | tool_calls=%d",
                    round_num + 1,
                    resp.finish_reason,
                    len(resp.content or ""),
                    len(resp.thinking or ""),
                    len(resp.tool_calls or []),
                )

                if resp.progress_hints:
                    for hint in resp.progress_hints:
                        logger.debug("  progress | phase=%r progress=%s detail=%r",
                                     hint.get("phase"), hint.get("progress"), hint.get("detail"))

                # ── 错误 ───────────────────────────────────────
                if resp.finish_reason == "error":
                    raise RuntimeError(f"模型错误: {resp.content}")

                # ── 思考过程 ───────────────────────────────────
                if resp.thinking and resp.finish_reason == "thinking":
                    thinking_parts.append(resp.thinking)
                    if not _has_shown_thinking:
                        _has_shown_thinking = True
                        if on_thinking:
                            on_thinking(resp.thinking, has_content=False)
                        if on_status:
                            on_status("thinking")
                    else:
                        if on_thinking:
                            on_thinking(resp.thinking, has_content=True)

                # ── 工具调用 ───────────────────────────────────
                if resp.tool_calls:
                    for tc in resp.tool_calls:
                        tname = tc.get("name") if isinstance(tc, dict) else getattr(tc, "name", None)
                        targs = tc.get("arguments") if isinstance(tc, dict) else getattr(tc, "arguments", {})
                        tool_calls.append((tname, targs))
                        logger.debug("LLM >> tool_call | round=%d | tool=%s", round_num + 1, tname)
                        if on_tool_call:
                            on_tool_call(tname, targs)

                # ── 流式文本 ───────────────────────────────────
                if resp.content and resp.finish_reason == "streaming":
                    full_response.append(resp.content)
                    if on_chunk:
                        on_chunk(resp.content)
                    if on_status:
                        on_status("streaming")

                # ── 非流式 stop ────────────────────────────────
                elif resp.finish_reason == "stop" and resp.content:
                    full_response.append(resp.content)
                    if on_chunk:
                        on_chunk(resp.content)

        # 思考完成日志
        if thinking_parts:
            full_thinking = "".join(thinking_parts)
            logger.debug("LLM >> thinking done | round=%d | total_len=%d",
                         round_num + 1, len(full_thinking))

        return ("".join(full_response), "".join(thinking_parts), tool_calls)

    def _build_messages(self, ws) -> list[dict]:
        """从工作区状态构建模型消息列表"""
        return [
            {"role": m.role, "content": m.content}
            for m in ws.messages
            if m.role in ("user", "assistant", "tool_result")
        ]

    async def _execute_tool(self, tool_name: str, args: dict,
                            workspace_id: str) -> str:
        """
        执行工具调用并返回结果

        支持的工具：
        - read: 读取文件
        - search / glob: 搜索文件
        - grep / search_content: 搜索内容
        - write: 写入文件
        - shell / bash: 执行命令
        - 默认: 返回"暂不支持"提示
        """
        if not tool_name:
            return "❌ 工具名为空"

        tool_name = tool_name.lower().strip()
        logger.info("Execute tool: %s | args_keys=%s", tool_name, list(args.keys()) if args else [])

        try:
            # ── 文件读取 ─────────────────────────────────
            if tool_name in ("read", "read_file"):
                path = args.get("file_path") or args.get("path") or args.get("filename", "")
                if not path:
                    return "❌ read: 缺少 file_path 参数"
                path = self._resolve_path(path)
                if not path.exists():
                    return f"❌ 文件不存在: {path}"
                try:
                    content = path.read_text(encoding="utf-8", errors="replace")
                    # 截断过长文件
                    max_chars = 8000
                    if len(content) > max_chars:
                        content = content[:max_chars] + f"\n... (截断，共 {len(content)} 字符)"
                    return content
                except Exception as e:
                    return f"❌ 读取失败: {e}"

            # ── 文件搜索 ─────────────────────────────────
            elif tool_name in ("glob", "search", "search_file", "find"):
                pattern = args.get("pattern") or args.get("glob") or args.get("query", "*")
                directory = args.get("directory") or args.get("path") or str(self.project_root)
                directory = self._resolve_path(directory)
                try:
                    matches = list(directory.glob(pattern))[:50]
                    if not matches:
                        return f"无匹配文件: pattern={pattern}"
                    return "\n".join(str(m.relative_to(self.project_root)) for m in matches)
                except Exception as e:
                    return f"❌ 搜索失败: {e}"

            # ── 内容搜索 ─────────────────────────────────
            elif tool_name in ("grep", "search_content", "rg"):
                pattern = args.get("pattern") or args.get("query", "")
                path = args.get("path") or str(self.project_root)
                if not pattern:
                    return "❌ grep: 缺少 pattern 参数"
                try:
                    result = subprocess.run(
                        ["grep", "-rn", "--include=*.py", "--include=*.md",
                         "--include=*.yaml", "--include=*.json",
                         pattern, path],
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

            # ── 文件写入 ─────────────────────────────────
            elif tool_name in ("write", "write_file"):
                path = args.get("file_path") or args.get("path", "")
                content = args.get("content", "")
                if not path:
                    return "❌ write: 缺少 file_path 参数"
                path = self._resolve_path(path)
                try:
                    path.parent.mkdir(parents=True, exist_ok=True)
                    path.write_text(content, encoding="utf-8")
                    return f"✅ 已写入: {path} ({len(content)} 字符)"
                except Exception as e:
                    return f"❌ 写入失败: {e}"

            # ── Shell 命令 ───────────────────────────────
            elif tool_name in ("shell", "bash", "command", "exec"):
                cmd = args.get("command") or args.get("cmd", "")
                if not cmd:
                    return "❌ shell: 缺少 command 参数"
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

            # ── 未知工具 ─────────────────────────────────
            else:
                return (f"⚠️ 工具 '{tool_name}' 暂未实现\n"
                        f"可用工具: read, glob, grep, write, shell")

        except Exception as e:
            logger.error("Tool execution error: %s | %s", tool_name, e)
            return f"❌ 工具执行异常: {e}"

    def _resolve_path(self, path_str: str) -> Path:
        """解析路径（支持相对/绝对路径）"""
        p = Path(path_str)
        if not p.is_absolute():
            p = self.project_root / p
        return p.resolve()
