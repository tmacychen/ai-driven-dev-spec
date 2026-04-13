"""
ADDS TUI 状态管理

AppState  — 全局状态（Agent 工作区管理器）
WorkspaceState — 单个 Agent 工作区状态
"""

from __future__ import annotations

import asyncio
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional


class WorkspaceStatus(str, Enum):
    ACTIVE = "active"
    WAITING = "waiting"
    PAUSED = "paused"
    COMPLETED = "completed"
    ERROR = "error"


@dataclass
class Message:
    """对话消息"""
    id: str
    role: str          # user | assistant | system | tool
    content: str
    timestamp: datetime = field(default_factory=datetime.now)
    tokens: int = 0
    collapsed: bool = False
    thinking: str = ""


@dataclass
class WorkspaceState:
    """单个 Agent 工作区状态"""
    workspace_id: str
    agent_role: str                          # pm/architect/developer/reviewer/tester
    task_context: str = ""
    status: WorkspaceStatus = WorkspaceStatus.ACTIVE
    messages: List[Message] = field(default_factory=list)
    token_used: int = 0
    token_budget: int = 128000
    streaming: bool = False
    draft: str = ""
    created_at: datetime = field(default_factory=datetime.now)
    last_active: datetime = field(default_factory=datetime.now)
    split_enabled: bool = False              # 是否开启分屏

    @property
    def label(self) -> str:
        """标签页显示名称"""
        role_labels = {
            "pm": "PM",
            "architect": "Arch",
            "developer": "Dev",
            "reviewer": "Rev",
            "tester": "Test",
        }
        short = role_labels.get(self.agent_role, self.agent_role[:4].title())
        ctx = self.task_context[:12] + "…" if len(self.task_context) > 12 else self.task_context
        return f"{short}-{ctx}" if ctx else short

    @property
    def token_pct(self) -> float:
        if self.token_budget <= 0:
            return 0.0
        return min(self.token_used / self.token_budget, 1.0)

    def touch(self) -> None:
        self.last_active = datetime.now()

    def add_message(self, role: str, content: str, thinking: str = "") -> Message:
        msg = Message(
            id=f"{self.workspace_id}-{len(self.messages)}",
            role=role,
            content=content,
            thinking=thinking,
        )
        self.messages.append(msg)
        self.touch()
        return msg


class AppState:
    """全局应用状态 — Agent 工作区管理器"""

    def __init__(self) -> None:
        self.workspaces: Dict[str, WorkspaceState] = {}
        self.active_workspace: Optional[str] = None
        self.permission_mode: str = "default"
        self._model_lock = asyncio.Lock()   # 流式互斥锁
        self._seq: Dict[str, int] = {}      # 每个角色的序号计数

    # ── Workspace 管理 ──────────────────────────────────────────

    def create_workspace(self, agent_role: str, task_context: str = "",
                         token_budget: int = 128000) -> WorkspaceState:
        """创建新的 Agent 工作区"""
        seq = self._seq.get(agent_role, 0) + 1
        self._seq[agent_role] = seq
        workspace_id = f"{agent_role}-{seq:03d}"

        ws = WorkspaceState(
            workspace_id=workspace_id,
            agent_role=agent_role,
            task_context=task_context,
            token_budget=token_budget,
        )
        self.workspaces[workspace_id] = ws
        if self.active_workspace is None:
            self.active_workspace = workspace_id
        return ws

    def get_active(self) -> Optional[WorkspaceState]:
        if self.active_workspace:
            return self.workspaces.get(self.active_workspace)
        return None

    def switch_to(self, workspace_id: str) -> bool:
        if workspace_id in self.workspaces:
            # 暂停当前
            if self.active_workspace and self.active_workspace != workspace_id:
                cur = self.workspaces.get(self.active_workspace)
                if cur and cur.status == WorkspaceStatus.ACTIVE:
                    cur.status = WorkspaceStatus.PAUSED
            self.active_workspace = workspace_id
            ws = self.workspaces[workspace_id]
            ws.status = WorkspaceStatus.ACTIVE
            ws.touch()
            return True
        return False

    def close_workspace(self, workspace_id: str) -> bool:
        if workspace_id not in self.workspaces:
            return False
        del self.workspaces[workspace_id]
        if self.active_workspace == workspace_id:
            # 切换到最后一个
            remaining = list(self.workspaces.keys())
            self.active_workspace = remaining[-1] if remaining else None
        return True

    def workspace_list(self) -> List[WorkspaceState]:
        return list(self.workspaces.values())

    @property
    def total_tokens(self) -> int:
        return sum(ws.token_used for ws in self.workspaces.values())

    @property
    def agent_count(self) -> int:
        return len(self.workspaces)
