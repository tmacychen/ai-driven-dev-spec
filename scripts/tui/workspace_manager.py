"""
WorkspaceManager — Agent 工作区管理器

负责：创建/切换/关闭 Workspace，持久化 .mem 文件，
      与 P0-2 SessionManager 和 P0-3 MemoryManager 集成
"""

from __future__ import annotations

import asyncio
import logging
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

    async def send_message(self, workspace_id: str, user_text: str,
                           on_chunk=None, on_done=None) -> Optional[str]:
        """
        向指定工作区发送消息，流式调用模型

        on_chunk(chunk: str) — 每个流式片段回调
        on_done(full: str)   — 完成回调（传入完整回复）
        """
        ws = self.state.workspaces.get(workspace_id)
        if not ws:
            return None
        if not self._model:
            # 模型未初始化，向 UI 反馈
            err = ws.add_message("system", "❌ 模型未初始化，请重启并选择模型")
            return None

        # 添加用户消息到状态
        ws.add_message("user", user_text)

        # 构建消息列表
        messages = [
            {"role": m.role, "content": m.content}
            for m in ws.messages
            if m.role in ("user", "assistant")
        ]

        system_prompt = self.get_system_prompt(ws.agent_role)
        full_response: list[str] = []

        ws.streaming = True
        try:
            async with self._model_lock:
                async for resp in self._model.chat(
                    messages,
                    system_prompt=system_prompt,
                    stream=True,
                ):
                    if resp.finish_reason == "error":
                        err_msg = f"❌ 错误: {resp.content}"
                        ws.add_message("system", err_msg)
                        if on_chunk:
                            on_chunk(err_msg)
                        break

                    # 流式片段
                    if resp.content and resp.finish_reason == "streaming":
                        full_response.append(resp.content)
                        if on_chunk:
                            on_chunk(resp.content)

                    # 非流式一次性返回（CLI 适配器，如 mmx）
                    elif resp.finish_reason == "stop" and resp.content:
                        full_response.append(resp.content)
                        if on_chunk:
                            on_chunk(resp.content)

        except Exception as e:
            logger.error(f"Model call failed: {e}")
            err_msg = f"❌ 调用失败: {e}"
            ws.add_message("system", err_msg)
            if on_chunk:
                on_chunk(err_msg)
        finally:
            ws.streaming = False

        full_text = "".join(full_response)
        if full_text:
            ws.add_message("assistant", full_text)
            # 更新 token 使用量（粗估）
            ws.token_used += len(user_text) // 4 + len(full_text) // 4

        if on_done:
            on_done(full_text)

        return full_text
