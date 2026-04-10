#!/usr/bin/env python3
"""
ADDS Session Manager — Session 文件管理

设计目标：
- 管理 .ses / .log / .mem 文件的生命周期
- 链式 Session 结构（Prev/Next 指针）
- Session 创建、读取、归档、恢复

文件格式参考：P0-2 路线图 — 文件体系设计

.ai/sessions/
├── 20260409-153000.ses       # Session 对话记录（活跃/摘要版）
├── 20260409-153000-ses1.log  # 工具输出 log
├── 20260409-153000-ses2.log  # 同一 session 第 2 个 log
├── 20260409-153000.mem       # 记忆归档（摘要 + 完整记录）
└── index.mem                 # 记忆索引（始终注入上下文）
"""

import json
import logging
import re
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Tuple

logger = logging.getLogger(__name__)


# ═══════════════════════════════════════════════════════════
# 数据结构
# ═══════════════════════════════════════════════════════════

@dataclass
class SessionHeader:
    """Session 文件头信息"""
    session_id: str          # 格式: YYYYMMDD-HHMMSS
    agent: str = ""          # 代理角色
    feature: str = ""        # 当前功能
    created: str = ""        # 创建时间
    status: str = "active"   # active | archived | restored
    prev_session: Optional[str] = None   # 前一个 session ID
    next_session: Optional[str] = None   # 后一个 session ID（归档时设置）

    def to_metadata(self) -> str:
        """生成 .ses 文件的元数据头部"""
        lines = [
            f"# Session: {self.session_id}",
            f"# Agent: {self.agent}",
            f"# Feature: {self.feature}",
            f"# Created: {self.created}",
            f"# Status: {self.status}",
        ]
        if self.prev_session:
            lines.append(f"# Prev: {self.prev_session}")
        if self.next_session:
            lines.append(f"# Next: {self.next_session}")
        return "\n".join(lines)

    @classmethod
    def from_metadata(cls, text: str) -> "SessionHeader":
        """从 .ses 文件的元数据头部解析"""
        data = {}
        for line in text.split("\n"):
            if line.startswith("# Session:"):
                data["session_id"] = line.split(":", 1)[1].strip()
            elif line.startswith("# Agent:"):
                data["agent"] = line.split(":", 1)[1].strip()
            elif line.startswith("# Feature:"):
                data["feature"] = line.split(":", 1)[1].strip()
            elif line.startswith("# Created:"):
                data["created"] = line.split(":", 1)[1].strip()
            elif line.startswith("# Status:"):
                data["status"] = line.split(":", 1)[1].strip()
            elif line.startswith("# Prev:"):
                data["prev_session"] = line.split(":", 1)[1].strip()
            elif line.startswith("# Next:"):
                data["next_session"] = line.split(":", 1)[1].strip()

        return cls(**data)


@dataclass
class MemoryHeader:
    """Memory (.mem) 文件头信息"""
    session_id: str
    agent: str = ""
    feature: str = ""
    created: str = ""
    archived: str = ""
    prev_mem: Optional[str] = None
    next_mem: Optional[str] = None

    def to_metadata(self) -> str:
        """生成 .mem 文件的元数据头部"""
        lines = [
            f"# Memory: {self.session_id}",
            f"# Agent: {self.agent} | Feature: {self.feature}",
            f"# Created: {self.created}",
            f"# Archived: {self.archived}",
        ]
        if self.prev_mem:
            lines.append(f"# Prev: {self.prev_mem}")
        else:
            lines.append("# Prev: null")
        if self.next_mem:
            lines.append(f"# Next: {self.next_mem}")
        else:
            lines.append("# Next: (待写入)")
        return "\n".join(lines)

    @classmethod
    def from_metadata(cls, text: str) -> "MemoryHeader":
        """从 .mem 文件的元数据头部解析"""
        data = {}
        for line in text.split("\n"):
            if line.startswith("# Memory:"):
                data["session_id"] = line.split(":", 1)[1].strip()
            elif line.startswith("# Agent:"):
                # Agent: xxx | Feature: yyy
                parts = line.split("|", 1)
                data["agent"] = parts[0].split(":", 1)[1].strip()
                if len(parts) > 1:
                    data["feature"] = parts[1].split(":", 1)[1].strip()
            elif line.startswith("# Created:"):
                data["created"] = line.split(":", 1)[1].strip()
            elif line.startswith("# Archived:"):
                data["archived"] = line.split(":", 1)[1].strip()
            elif line.startswith("# Prev:"):
                val = line.split(":", 1)[1].strip()
                data["prev_mem"] = None if val == "null" else val
            elif line.startswith("# Next:"):
                val = line.split(":", 1)[1].strip()
                if val in ("(待写入)", "null", ""):
                    data["next_mem"] = None
                else:
                    data["next_mem"] = val
        return cls(**data)


# ═══════════════════════════════════════════════════════════
# Session Manager
# ═══════════════════════════════════════════════════════════

class SessionManager:
    """Session 文件管理器

    核心职责：
    1. 创建新 Session（.ses 文件 + 头信息）
    2. 追加消息到活跃 Session
    3. 保存工具输出到 .log 文件
    4. 归档 Session（.ses → .mem，含 LLM 摘要）
    5. 链式指针维护（Prev/Next）
    6. 恢复 Session（.mem → .ses）
    """

    def __init__(self, sessions_dir: str = ".ai/sessions"):
        self.sessions_dir = Path(sessions_dir)
        self.sessions_dir.mkdir(parents=True, exist_ok=True)

        self._current_session_id: Optional[str] = None
        self._current_header: Optional[SessionHeader] = None
        self._log_counter: int = 0

    # ──── Session 创建 ────

    def create_session(self, agent: str = "", feature: str = "") -> str:
        """创建新 Session

        Args:
            agent: 代理角色 (pm/architect/developer/tester/reviewer)
            feature: 当前功能名

        Returns:
            session_id (格式: YYYYMMDD-HHMMSS)
        """
        session_id = datetime.now().strftime("%Y%m%d-%H%M%S")

        # 确保不与已有 session 冲突（同一秒内创建多个 session 时）
        while self._ses_path(session_id).exists():
            # 追加 -2, -3 等后缀
            base = datetime.now().strftime("%Y%m%d-%H%M%S")
            # 计数器递增
            existing = list(self.sessions_dir.glob(f"{base}*.ses"))
            if existing:
                session_id = f"{base}-{len(existing)+1}"
            else:
                break

        # 查找前一个 session
        prev_session = self._find_latest_session_id(exclude=session_id)

        header = SessionHeader(
            session_id=session_id,
            agent=agent,
            feature=feature,
            created=datetime.now().isoformat(),
            status="active",
            prev_session=prev_session,
        )

        # 写入 .ses 文件头
        ses_path = self._ses_path(session_id)
        content = header.to_metadata() + "\n\n---\n\n## Messages\n"
        ses_path.write_text(content, encoding="utf-8")

        self._current_session_id = session_id
        self._current_header = header
        self._log_counter = 0

        # 更新前一个 session 的 Next 指针
        if prev_session:
            self._update_next_pointer(prev_session, session_id)

        logger.info(f"Session created: {session_id} (agent={agent}, feature={feature})")
        return session_id

    # ──── 消息追加 ────

    def append_message(self, role: str, content: str,
                       strategy: str = "", priority: str = "",
                       file_ref: str = "") -> None:
        """追加消息到当前 Session

        Args:
            role: 消息角色 (user/assistant/tool_call/tool_result)
            content: 消息内容
            strategy: 摘要策略标记 (tool_filter/llm_analyze/keep_full)
            priority: 优先级标记 (high/normal)
            file_ref: 文件快照引用 (file_ref 元数据)
        """
        if not self._current_session_id:
            logger.warning("No active session, message ignored")
            return

        ses_path = self._ses_path(self._current_session_id)

        # 构建消息块
        msg_lines = [f"\n### [{role}]"]
        msg_lines.append(content)

        # 附加元数据注释
        meta = []
        if strategy:
            meta.append(f"strategy: {strategy}")
        if priority:
            meta.append(f"priority: {priority}")
        if file_ref:
            meta.append(f"file_ref: {file_ref}")
        if meta:
            msg_lines.append(f"<!-- {' | '.join(meta)} -->")

        msg_lines.append("")  # 空行

        # 追加写入
        with open(ses_path, "a", encoding="utf-8") as f:
            f.write("\n".join(msg_lines))

    def save_tool_output(self, content: str, summary: str = "",
                         strategy: str = "tool_filter") -> str:
        """保存工具输出到 .log 文件，并在 .ses 中留下引用

        Args:
            content: 完整工具输出
            summary: 压缩后的摘要
            strategy: 使用的压缩策略

        Returns:
            log 文件名 (如 "20260409-153000-ses1.log")
        """
        if not self._current_session_id:
            logger.warning("No active session, tool output ignored")
            return ""

        self._log_counter += 1
        log_filename = f"{self._current_session_id}-ses{self._log_counter}.log"
        log_path = self.sessions_dir / log_filename

        # 写入 .log 文件
        log_path.write_text(content, encoding="utf-8")

        # 在 .ses 中追加引用 + 摘要
        placeholder = f"详见 `{log_filename}`"
        if summary:
            msg = f"{placeholder}\n摘要: {summary}"
        else:
            msg = placeholder

        self.append_message("tool_result", msg, strategy=strategy)

        logger.debug(f"Tool output saved: {log_filename} ({len(content)} chars)")
        return log_filename

    # ──── Session 读取 ────

    def read_session(self, session_id: str) -> Tuple[SessionHeader, str]:
        """读取 Session 内容

        Returns:
            (header, body_text)
        """
        ses_path = self._ses_path(session_id)
        if not ses_path.exists():
            raise FileNotFoundError(f"Session not found: {ses_path}")

        text = ses_path.read_text(encoding="utf-8")
        header, body = self._split_header_body(text)
        return header, body

    def read_log(self, log_filename: str) -> str:
        """读取 .log 文件内容"""
        log_path = self.sessions_dir / log_filename
        if not log_path.exists():
            raise FileNotFoundError(f"Log not found: {log_path}")
        return log_path.read_text(encoding="utf-8")

    def reconstruct_full_session(self, session_id: str) -> str:
        """重建完整 Session（将 .log 引用替换为实际内容）

        用于 Layer2 归档前合并 .ses + .log 文件。

        Args:
            session_id: Session ID

        Returns:
            完整的 Session 文本（含所有工具输出）
        """
        header, body = self.read_session(session_id)

        # 查找所有 log 引用并替换
        log_pattern = re.compile(r'详见 `(\S+\.log)`')
        lines = body.split("\n")
        reconstructed = []

        i = 0
        while i < len(lines):
            line = lines[i]
            match = log_pattern.search(line)
            if match:
                log_filename = match.group(1)
                try:
                    log_content = self.read_log(log_filename)
                    reconstructed.append(f"### [tool_result — 完整输出 from {log_filename}]")
                    reconstructed.append(log_content)
                except FileNotFoundError:
                    reconstructed.append(f"⚠️ Log file not found: {log_filename}")
            else:
                reconstructed.append(line)
            i += 1

        return header.to_metadata() + "\n\n---\n\n" + "\n".join(reconstructed)

    # ──── Session 归档 ────

    def archive_session(self, summary: str, full_record: str = "") -> str:
        """归档当前 Session → 生成 .mem 文件

        操作：
        1. 合并 .ses + .log → 完整记录
        2. 生成 .mem 文件（摘要 + 完整记录 + 链式指针）
        3. 回写 .ses 为摘要版

        Args:
            summary: LLM 生成的结构化摘要
            full_record: 完整记录（如果为空，自动从 .ses + .log 重建）

        Returns:
            .mem 文件路径
        """
        if not self._current_session_id:
            raise RuntimeError("No active session to archive")

        session_id = self._current_session_id

        # Step 1: 获取完整记录
        if not full_record:
            full_record = self.reconstruct_full_session(session_id)

        # Step 2: 生成 .mem 文件
        header = self._current_header
        prev_mem = self._find_latest_mem_id(exclude=session_id)

        mem_header = MemoryHeader(
            session_id=session_id,
            agent=header.agent if header else "",
            feature=header.feature if header else "",
            created=header.created if header else "",
            archived=datetime.now().isoformat(),
            prev_mem=prev_mem,
        )

        mem_content = mem_header.to_metadata() + f"""

---

## 结构化摘要（由 LLM 生成）

{summary}

---

## 完整记录（含工具输出详情）

{full_record}
"""

        mem_path = self._mem_path(session_id)
        mem_path.write_text(mem_content, encoding="utf-8")

        # Step 3: 回写 .ses 为摘要版
        ses_summary = header.to_metadata() + f"\n# Status: archived\n\n---\n\n"
        ses_summary += f"## 摘要\n\n{summary}\n\n"
        ses_summary += f"**完整记录**: `{session_id}.mem`\n"
        if prev_mem:
            ses_summary += f"**前一个 session**: `{prev_mem}.mem`\n"

        ses_path = self._ses_path(session_id)
        ses_path.write_text(ses_summary, encoding="utf-8")

        # 更新 header
        header.status = "archived"
        header.next_session = None  # 下一个 session 由下一个 create 设置

        # 更新前一个 .mem 的 Next 指针
        if prev_mem:
            self._update_mem_next_pointer(prev_mem, session_id)

        logger.info(f"Session archived: {session_id} → {mem_path.name}")
        self._current_session_id = None
        self._current_header = None

        return str(mem_path)

    # ──── Session 恢复 ────

    def restore_session(self, session_id: str) -> str:
        """从 .mem 文件恢复 Session

        Args:
            session_id: 要恢复的 Session ID

        Returns:
            恢复后的 .ses 文件路径
        """
        mem_path = self._mem_path(session_id)
        if not mem_path.exists():
            raise FileNotFoundError(f"Memory file not found: {mem_path}")

        mem_content = mem_path.read_text(encoding="utf-8")

        # 解析 .mem 头部
        mem_header, body = self._split_mem_header(mem_content)

        # 提取完整记录区
        full_record_match = re.search(
            r'## 完整记录.*?\n\n(.*)',
            body, re.DOTALL
        )
        if full_record_match:
            full_record = full_record_match.group(1).strip()
        else:
            full_record = body

        # 生成恢复的 .ses 文件
        ses_header = SessionHeader(
            session_id=session_id,
            agent=mem_header.agent,
            feature=mem_header.feature,
            created=mem_header.created,
            status="restored",
            prev_session=mem_header.prev_mem,
        )

        ses_content = ses_header.to_metadata() + "\n\n---\n\n" + full_record

        ses_path = self._ses_path(session_id)
        ses_path.write_text(ses_content, encoding="utf-8")

        logger.info(f"Session restored: {session_id}")
        return str(ses_path)

    # ──── 查询方法 ────

    def get_current_session_id(self) -> Optional[str]:
        """获取当前活跃 Session ID"""
        return self._current_session_id

    def get_prev_session_summary(self) -> Optional[str]:
        """获取上一个 Session 的摘要（用于注入新 session 上下文）

        Returns:
            上一个 .mem 文件的摘要区内容，或 None
        """
        if not self._current_header or not self._current_header.prev_session:
            return None

        prev_id = self._current_header.prev_session
        mem_path = self._mem_path(prev_id)
        if not mem_path.exists():
            # 尝试从 .ses 读取摘要版
            try:
                header, body = self.read_session(prev_id)
                if body:
                    return body[:2000]
            except FileNotFoundError:
                return None
            return None

        try:
            mem_content = mem_path.read_text(encoding="utf-8")
            _, body = self._split_mem_header(mem_content)

            # 提取摘要区
            summary_match = re.search(
                r'## 结构化摘要.*?\n\n(.*?)(?=\n---\n## 完整记录)',
                body, re.DOTALL
            )
            if summary_match:
                return summary_match.group(1).strip()
            # 回退：返回 body 前 2000 字符
            return body[:2000] if body else None
        except Exception as e:
            logger.warning(f"Failed to read prev session summary: {e}")
            return None

    def list_sessions(self) -> List[Dict]:
        """列出所有 Session 的元数据"""
        sessions = []
        for ses_path in sorted(self.sessions_dir.glob("*.ses")):
            session_id = ses_path.stem
            try:
                header, _ = self.read_session(session_id)
                sessions.append({
                    "session_id": session_id,
                    "agent": header.agent,
                    "feature": header.feature,
                    "created": header.created,
                    "status": header.status,
                    "prev": header.prev_session,
                    "next": header.next_session,
                })
            except Exception as e:
                sessions.append({
                    "session_id": session_id,
                    "error": str(e),
                })
        return sessions

    def list_logs(self, session_id: str) -> List[str]:
        """列出某个 Session 的所有 .log 文件"""
        return sorted(
            p.name for p in self.sessions_dir.glob(f"{session_id}-ses*.log")
        )

    def session_exists(self, session_id: str) -> bool:
        """Session 是否存在"""
        return self._ses_path(session_id).exists()

    # ──── 内部方法 ────

    def _ses_path(self, session_id: str) -> Path:
        return self.sessions_dir / f"{session_id}.ses"

    def _mem_path(self, session_id: str) -> Path:
        return self.sessions_dir / f"{session_id}.mem"

    def _split_header_body(self, text: str) -> Tuple[SessionHeader, str]:
        """分割 .ses 文件的头部元数据和正文"""
        metadata_lines = []
        body_start = 0
        for i, line in enumerate(text.split("\n")):
            if line.startswith("# ") and not line.startswith("# Session:") and body_start == 0:
                # 仍在头部
                pass
            elif line.startswith("# "):
                metadata_lines.append(line)
            elif line.strip() == "---":
                body_start = i + 1
                break
            else:
                metadata_lines.append(line)

        header = SessionHeader.from_metadata("\n".join(metadata_lines))
        body = "\n".join(text.split("\n")[body_start:])
        return header, body.strip()

    def _split_mem_header(self, text: str) -> Tuple[MemoryHeader, str]:
        """分割 .mem 文件的头部元数据和正文"""
        metadata_lines = []
        body_start = 0
        for i, line in enumerate(text.split("\n")):
            if line.startswith("# ") or (line.startswith("#") and not line.startswith("##")):
                metadata_lines.append(line)
            elif line.strip() == "---":
                body_start = i + 1
                break

        header = MemoryHeader.from_metadata("\n".join(metadata_lines))
        body = "\n".join(text.split("\n")[body_start:])
        return header, body.strip()

    def _find_latest_session_id(self, exclude: str = "") -> Optional[str]:
        """查找最新的 Session ID（用于设置 Prev 指针）"""
        ses_files = sorted(self.sessions_dir.glob("*.ses"), reverse=True)
        for ses_path in ses_files:
            sid = ses_path.stem
            if sid != exclude:
                return sid
        return None

    def _find_latest_mem_id(self, exclude: str = "") -> Optional[str]:
        """查找最新的 .mem 文件 ID"""
        mem_files = sorted(self.sessions_dir.glob("*.mem"), reverse=True)
        for mem_path in mem_files:
            mid = mem_path.stem
            if mid != exclude and mid != "index":
                return mid
        return None

    def _update_next_pointer(self, session_id: str, next_id: str) -> None:
        """更新 .ses 文件的 Next 指针"""
        ses_path = self._ses_path(session_id)
        if not ses_path.exists():
            return
        content = ses_path.read_text(encoding="utf-8")
        # 替换或追加 Next 行
        if "# Next:" in content:
            content = re.sub(r'# Next:.*', f'# Next: {next_id}', content)
        else:
            content = content.replace(
                "# Status: active",
                f"# Status: active\n# Next: {next_id}",
            )
        ses_path.write_text(content, encoding="utf-8")

    def _update_mem_next_pointer(self, mem_id: str, next_id: str) -> None:
        """更新 .mem 文件的 Next 指针"""
        mem_path = self._mem_path(mem_id)
        if not mem_path.exists():
            return
        content = mem_path.read_text(encoding="utf-8")
        content = re.sub(r'# Next: \(待写入\)', f'# Next: {next_id}.mem', content)
        content = re.sub(r'# Next: null', f'# Next: {next_id}.mem', content)
        mem_path.write_text(content, encoding="utf-8")


# ═══════════════════════════════════════════════════════════
# 单元测试
# ═══════════════════════════════════════════════════════════

if __name__ == "__main__":
    import tempfile
    import shutil

    logging.basicConfig(level=logging.DEBUG)

    # 使用临时目录测试
    tmp = tempfile.mkdtemp(prefix="adds_test_")
    try:
        mgr = SessionManager(sessions_dir=tmp)

        # 创建第一个 session
        sid1 = mgr.create_session(agent="developer", feature="auth")
        print(f"Session 1: {sid1}")

        # 追加消息
        mgr.append_message("user", "实现用户认证功能")
        mgr.append_message("assistant", "我来分析需求...")

        # 保存工具输出
        log1 = mgr.save_tool_output(
            "test_auth.py::test_login PASSED\n"
            "test_auth.py::test_logout PASSED\n"
            "2 passed in 1.5s",
            summary="2 passed, 0 failed",
            strategy="tool_filter",
        )
        print(f"Log saved: {log1}")

        # 追加高价值消息
        mgr.append_message(
            "assistant",
            "任务完成。结论：用户认证功能已实现",
            strategy="llm_analyze",
            priority="high",
        )

        # 归档
        summary = """### 关键决策\n- 使用 JWT 进行用户认证\n- 密码使用 bcrypt 哈希存储"""
        mem_path = mgr.archive_session(summary=summary)
        print(f"Archived: {mem_path}")

        # 创建第二个 session
        sid2 = mgr.create_session(agent="developer", feature="dashboard")
        print(f"Session 2: {sid2}")

        # 获取上一个 session 摘要
        prev_summary = mgr.get_prev_session_summary()
        print(f"Prev summary: {prev_summary[:100] if prev_summary else 'None'}...")

        # 列出 sessions
        sessions = mgr.list_sessions()
        for s in sessions:
            print(f"  {s}")

        # 恢复第一个 session
        restored = mgr.restore_session(sid1)
        print(f"Restored: {restored}")

    finally:
        shutil.rmtree(tmp)
        print("\n✅ SessionManager tests passed")
