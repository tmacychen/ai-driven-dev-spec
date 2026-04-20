"""
WorkspaceManager — TUI 工作区管理器（基于 AgentCore 共享核心层）

职责：创建/切换/关闭 Workspace，将 UI 回调连接到 AgentCore。
核心逻辑（模型调用、工具执行、韧性增强、Session、记忆、权限等）
全部由 AgentCore 提供，此文件只做 TUI 界面适配。
"""

from __future__ import annotations

import asyncio
import logging
from pathlib import Path
from typing import Optional

from agent_core import AgentCore, AgentCallbacks, BUILTIN_ROLES
from permission_manager import PermissionDecision
from tui.state import AppState, WorkspaceState, WorkspaceStatus

logger = logging.getLogger(__name__)


class WorkspaceManager:
    """管理所有 Agent 工作区 — AgentCore 的 TUI 适配层"""

    def __init__(self, app_state: AppState, project_root: str = ".") -> None:
        self.state = app_state
        self.project_root = Path(project_root)
        self._model = None
        self._cores: dict[str, AgentCore] = {}  # workspace_id → AgentCore

    def set_model(self, model) -> None:
        """注入共享模型实例"""
        self._model = model
        if model:
            ctx = model.get_context_window()
            self.state.context_window = ctx

    def _get_or_create_core(self, workspace_id: str) -> Optional[AgentCore]:
        """获取或创建 AgentCore 实例"""
        if workspace_id in self._cores:
            return self._cores[workspace_id]

        ws = self.state.workspaces.get(workspace_id)
        if not ws or not self._model:
            return None

        core = AgentCore(
            model=self._model,
            project_root=str(self.project_root),
            agent_role=ws.agent_role,
            permission_mode=self.state.permission_mode,
        )
        core.init_session()
        self._cores[workspace_id] = core
        return core

    def create_workspace(self, agent_role: str, task_context: str = "") -> WorkspaceState:
        """创建新的 Agent 工作区"""
        ctx_window = self._model.get_context_window() if self._model else 128000
        ws = self.state.create_workspace(
            agent_role=agent_role,
            task_context=task_context,
            token_budget=ctx_window,
        )
        logger.info("Workspace created: %s (%s)", ws.workspace_id, agent_role)
        return ws

    def switch_workspace(self, workspace_id: str) -> bool:
        """切换到指定工作区"""
        ok = self.state.switch_to(workspace_id)
        if ok:
            logger.debug("Switched to workspace: %s", workspace_id)
        return ok

    def close_workspace(self, workspace_id: str) -> bool:
        """关闭工作区（归档 .mem）"""
        ws = self.state.workspaces.get(workspace_id)
        if not ws:
            return False

        # 通过 AgentCore 归档
        core = self._cores.pop(workspace_id, None)
        if core:
            core.archive_session()

        ws.status = WorkspaceStatus.COMPLETED
        ok = self.state.close_workspace(workspace_id)
        logger.info("Workspace closed: %s", workspace_id)
        return ok

    # ── Agent Loop 入口 ─────────────────────────────────

    async def send_message(self, workspace_id: str, user_text: str,
                           on_chunk=None, on_done=None,
                           on_thinking=None, on_tool_call=None,
                           on_status=None) -> Optional[str]:
        """
        向指定工作区发送消息 — 委托给 AgentCore
        """
        core = self._get_or_create_core(workspace_id)
        if not core:
            return None

        ws = self.state.workspaces.get(workspace_id)
        if not ws:
            return None

        # 构建 TUI 回调
        callbacks = AgentCallbacks(
            on_chunk=on_chunk,
            on_done=on_done,
            on_thinking=on_thinking,
            on_tool_call=on_tool_call,
            on_status=on_status,
            on_error=lambda msg: (
                ws.add_message("system", msg) if ws else None,
                on_chunk(msg) if on_chunk else None,
            )[1],
            on_warning=lambda msg: on_status(f"warning:{msg}") if on_status else None,
            on_permission_ask=self._make_permission_callback(workspace_id),
            on_compact=lambda strategy, saved: logger.info(
                "Compact %s: saved %d tokens", strategy, saved),
            on_continuation=lambda n: logger.info("Continuation attempt %d", n),
        )

        ws.streaming = True
        try:
            result = await core.send_message(user_text, callbacks=callbacks)
            # 同步 token 统计到 WorkspaceState
            ws.token_used = core.budget.used
            return result
        finally:
            ws.streaming = False

    def _make_permission_callback(self, workspace_id: str):
        """创建权限确认回调 — 通知 TUI 显示确认对话框"""
        def _ask_permission(decision: PermissionDecision) -> bool:
            # TUI 权限确认：通过 PermissionSidebar 实现
            # 目前先自动放行（TODO: 接入 PermissionSidebar 交互确认）
            logger.info("Permission auto-allowed: %s (%s)", decision.tool, decision.command)
            return True
        return _ask_permission

    # ── 便捷方法 ────────────────────────────────────────

    def get_system_prompt(self, agent_role: str) -> str:
        """获取角色系统提示词"""
        core = AgentCore.__new__(AgentCore)
        return BUILTIN_ROLES.get(agent_role, f"你是一个 {agent_role} 角色的 AI 助手")

    def get_workspace_stats(self, workspace_id: str) -> dict:
        """获取工作区统计"""
        core = self._cores.get(workspace_id)
        if core:
            return core.get_stats()
        return {}
