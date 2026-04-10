#!/usr/bin/env python3
"""
ADDS 权限管理器 — P0-4 命令批准机制

三级权限模型：Allow / Ask / Deny
权限来源优先级：会话 > 命令行 > 项目设置 > 用户设置
模式匹配：工具名 + 命令模式 + 路径模式
死循环防护：同一工具连续拒绝 3 次后冷却 30 秒
四种权限模式：default / plan / auto / bypass

参考：Claude Code 第16章 - 权限系统
"""

import fnmatch
import json
import logging
import time
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Optional, Dict, List, Tuple

logger = logging.getLogger(__name__)


# ═══════════════════════════════════════════════════════════════
# 权限级别
# ═══════════════════════════════════════════════════════════════

class PermissionLevel(Enum):
    """权限级别"""
    ALLOW = "allow"   # 自动放行
    ASK = "ask"       # 需要用户确认
    DENY = "deny"     # 直接拒绝


class PermissionMode(Enum):
    """权限模式"""
    DEFAULT = "default"   # 敏感操作逐一确认（推荐）
    PLAN = "plan"         # 只能读不能写（探索阶段）
    AUTO = "auto"         # AI 分类器自动决策（高级）
    BYPASS = "bypass"     # 所有操作自动放行（危险）


# ═══════════════════════════════════════════════════════════════
# 权限决策结果
# ═══════════════════════════════════════════════════════════════

@dataclass
class PermissionDecision:
    """权限决策结果"""
    level: PermissionLevel
    tool: str                    # 工具名 (bash, read, write)
    command: str                 # 完整命令
    matched_rule: Optional[str]  # 匹配到的规则
    source: str                  # 规则来源 (session/cli/project/user)
    reason: str = ""             # 决策原因

    @property
    def is_allowed(self) -> bool:
        return self.level == PermissionLevel.ALLOW

    @property
    def needs_confirmation(self) -> bool:
        return self.level == PermissionLevel.ASK

    @property
    def is_denied(self) -> bool:
        return self.level == PermissionLevel.DENY

    def __str__(self) -> str:
        icon = {"allow": "✅", "ask": "⚠️", "deny": "🚫"}[self.level.value]
        return f"{icon} {self.level.value.upper()}: {self.tool}({self.command}) [{self.source}]"


# ═══════════════════════════════════════════════════════════════
# 死循环防护
# ═══════════════════════════════════════════════════════════════

@dataclass
class CooldownState:
    """死循环防护状态"""
    consecutive_denies: Dict[str, int] = field(default_factory=dict)  # tool → 连续拒绝次数
    last_deny_time: Dict[str, float] = field(default_factory=dict)    # tool → 上次拒绝时间
    max_consecutive: int = 3      # 连续拒绝上限
    cooldown_seconds: float = 30  # 冷却时间（秒）

    def record_deny(self, tool: str) -> None:
        """记录一次拒绝"""
        self.consecutive_denies[tool] = self.consecutive_denies.get(tool, 0) + 1
        self.last_deny_time[tool] = time.time()

    def record_allow(self, tool: str) -> None:
        """记录一次放行（重置拒绝计数）"""
        self.consecutive_denies.pop(tool, None)
        self.last_deny_time.pop(tool, None)

    def is_in_cooldown(self, tool: str) -> bool:
        """检查工具是否在冷却期"""
        count = self.consecutive_denies.get(tool, 0)
        if count < self.max_consecutive:
            return False

        last_time = self.last_deny_time.get(tool, 0)
        elapsed = time.time() - last_time
        if elapsed < self.cooldown_seconds:
            return True

        # 冷却期已过，重置
        self.consecutive_denies.pop(tool, None)
        self.last_deny_time.pop(tool, None)
        return False

    def cooldown_remaining(self, tool: str) -> float:
        """剩余冷却时间（秒）"""
        last_time = self.last_deny_time.get(tool, 0)
        elapsed = time.time() - last_time
        return max(0, self.cooldown_seconds - elapsed)


# ═══════════════════════════════════════════════════════════════
# 权限规则匹配
# ═══════════════════════════════════════════════════════════════

def match_rule(pattern: str, tool: str, command: str) -> bool:
    """
    匹配权限规则

    规则格式: tool(command_pattern)
    例如: bash(rm*), read(*), write(./*)

    Args:
        pattern: 权限规则模式
        tool: 工具名
        command: 命令内容

    Returns:
        是否匹配
    """
    # 解析 tool(command_pattern) 格式
    if "(" in pattern and pattern.endswith(")"):
        rule_tool, rule_cmd = pattern.split("(", 1)
        rule_cmd = rule_cmd.rstrip(")")
    else:
        # 没有 () 简写，匹配整个工具
        rule_tool = pattern
        rule_cmd = "*"

    # 工具名匹配（精确）
    if rule_tool != tool:
        return False

    # 命令模式匹配（fnmatch 通配符）
    return fnmatch.fnmatch(command, rule_cmd)


# ═══════════════════════════════════════════════════════════════
# 会话级权限覆盖
# ═══════════════════════════════════════════════════════════════

class SessionOverrides:
    """会话级权限覆盖（优先级最高）"""

    def __init__(self):
        self._allowed: List[str] = []   # 本次会话已允许的命令
        self._denied: List[str] = []    # 本次会话已拒绝的命令

    def allow(self, pattern: str) -> None:
        """添加会话级允许规则"""
        self._allowed.append(pattern)

    def deny(self, pattern: str) -> None:
        """添加会话级拒绝规则"""
        self._denied.append(pattern)

    def check(self, tool: str, command: str) -> Optional[PermissionLevel]:
        """检查会话级覆盖，返回 None 表示无覆盖"""
        for pattern in self._denied:
            if match_rule(pattern, tool, command):
                return PermissionLevel.DENY

        for pattern in self._allowed:
            if match_rule(pattern, tool, command):
                return PermissionLevel.ALLOW

        return None


# ═══════════════════════════════════════════════════════════════
# 权限管理器
# ═══════════════════════════════════════════════════════════════

class PermissionManager:
    """
    权限管理器 — P0-4

    三级权限模型：Allow / Ask / Deny
    权限来源优先级：会话 > 命令行 > 项目设置 > 用户设置
    死循环防护：同一工具连续拒绝 3 次后冷却 30 秒
    """

    # plan 模式下的只读工具列表
    READONLY_TOOLS = {"read", "ls", "cat", "head", "tail", "wc", "grep", "find", "git_status", "git_log", "git_diff"}
    READONLY_BASH_PATTERNS = [
        "ls*", "cat*", "head*", "tail*", "wc*", "grep*", "find*",
        "git status*", "git log*", "git diff*", "git branch*",
        "python -c *", "python3 -c *",
    ]

    # auto 模式的自动放行模式（低风险）
    AUTO_ALLOW_PATTERNS = [
        "bash(ls*)", "bash(cat*)", "bash(head*)", "bash(tail*)",
        "bash(wc*)", "bash(grep*)", "bash(find*)",
        "bash(python*)", "bash(pytest*)",
        "bash(git status*)", "bash(git log*)", "bash(git diff*)",
        "bash(git add*)", "bash(git branch*)",
        "read(*)",
    ]

    # auto 模式的自动拒绝模式（高风险）
    AUTO_DENY_PATTERNS = [
        "bash(sudo*)", "bash(su *)", "bash(chmod 777*)",
        "bash(mkfs*)", "bash(dd*)",
        "bash(nc *)", "bash(iptables*)",
        "write(/etc/*)", "write(/System/*)", "write(/usr/*)",
    ]

    def __init__(self, project_root: str = ".", mode: str = "default",
                 session_overrides: Optional[SessionOverrides] = None):
        """
        初始化权限管理器

        Args:
            project_root: 项目根目录
            mode: 权限模式 (default/plan/auto/bypass)
            session_overrides: 会话级覆盖
        """
        self.project_root = Path(project_root)
        self.mode = PermissionMode(mode)
        self.session = session_overrides or SessionOverrides()
        self.cooldown = CooldownState()

        # 加载权限规则（项目设置 + 用户设置）
        self._rules = self._load_rules()

        # 决策日志
        self._decision_log: List[PermissionDecision] = []

    def _load_rules(self) -> Dict[PermissionLevel, List[Tuple[str, str]]]:
        """
        加载权限规则

        权限来源优先级：项目设置(.ai/settings.json) > 用户设置(~/.adds/settings.json)

        Returns:
            {PermissionLevel: [(pattern, source), ...]}
        """
        rules: Dict[PermissionLevel, List[Tuple[str, str]]] = {
            PermissionLevel.ALLOW: [],
            PermissionLevel.ASK: [],
            PermissionLevel.DENY: [],
        }

        # 加载项目设置
        project_settings = self._load_settings_file(
            self.project_root / ".ai" / "settings.json"
        )
        if project_settings:
            self._parse_rules(project_settings, "project", rules)

        # 加载用户设置（低优先级，不覆盖项目设置）
        user_settings = self._load_settings_file(
            Path.home() / ".adds" / "settings.json"
        )
        if user_settings:
            self._parse_rules(user_settings, "user", rules)

        # 如果没有任何规则，使用默认规则
        if not any(rules.values()):
            self._apply_default_rules(rules)

        return rules

    def _load_settings_file(self, path: Path) -> Optional[dict]:
        """加载 JSON 设置文件"""
        try:
            if path.exists():
                with open(path, "r", encoding="utf-8") as f:
                    data = json.load(f)
                return data.get("permissions", data)
        except (json.JSONDecodeError, OSError) as e:
            logger.warning(f"Failed to load settings from {path}: {e}")
        return None

    def _parse_rules(self, settings: dict, source: str,
                     rules: Dict[PermissionLevel, List[Tuple[str, str]]]) -> None:
        """解析权限规则"""
        perm_settings = settings.get("permissions", settings)
        rules_config = perm_settings.get("rules", {})

        for level_name in ("allow", "ask", "deny"):
            level = PermissionLevel(level_name)
            patterns = rules_config.get(level_name, [])
            for pattern in patterns:
                rules[level].append((pattern, source))

    def _apply_default_rules(self, rules: Dict[PermissionLevel, List[Tuple[str, str]]]) -> None:
        """应用默认权限规则"""
        default_allow = [
            "bash(ls*)", "bash(cat*)", "bash(head*)", "bash(tail*)",
            "bash(wc*)", "bash(grep*)", "bash(find*)", "bash(cp*)", "bash(mv*)",
            "bash(python*)", "bash(pytest*)",
            "bash(git status*)", "bash(git log*)", "bash(git diff*)", "bash(git add*)",
            "bash(git branch*)",
            "read(*)", "write(./*)",
        ]
        default_ask = [
            "bash(rm*)", "bash(npm install*)", "bash(pip install*)",
            "bash(git push*)", "bash(git commit*)", "bash(git checkout*)",
            "write(../../*)",
        ]
        default_deny = [
            "bash(sudo*)", "bash(su *)", "bash(chmod 777*)",
            "bash(mkfs*)", "bash(dd*)",
            "bash(nc *)", "bash(iptables*)",
            "write(/etc/*)", "write(/System/*)", "write(/usr/*)",
        ]

        for pattern in default_allow:
            rules[PermissionLevel.ALLOW].append((pattern, "default"))
        for pattern in default_ask:
            rules[PermissionLevel.ASK].append((pattern, "default"))
        for pattern in default_deny:
            rules[PermissionLevel.DENY].append((pattern, "default"))

    def check(self, tool: str, command: str) -> PermissionDecision:
        """
        检查权限

        Args:
            tool: 工具名 (bash, read, write)
            command: 命令内容

        Returns:
            PermissionDecision
        """
        # bypass 模式：全部放行
        if self.mode == PermissionMode.BYPASS:
            return PermissionDecision(
                level=PermissionLevel.ALLOW,
                tool=tool, command=command,
                matched_rule=None,
                source="mode:bypass",
                reason="bypass 模式自动放行",
            )

        # 死循环防护
        if self.cooldown.is_in_cooldown(tool):
            remaining = self.cooldown.cooldown_remaining(tool)
            return PermissionDecision(
                level=PermissionLevel.DENY,
                tool=tool, command=command,
                matched_rule=None,
                source="cooldown",
                reason=f"工具 {tool} 连续被拒 {self.cooldown.max_consecutive} 次，"
                       f"冷却中（剩余 {remaining:.0f}s）",
            )

        # plan 模式：只读放行，其他拒绝
        if self.mode == PermissionMode.PLAN:
            if self._is_readonly(tool, command):
                decision = PermissionDecision(
                    level=PermissionLevel.ALLOW,
                    tool=tool, command=command,
                    matched_rule="readonly",
                    source="mode:plan",
                    reason="plan 模式允许只读操作",
                )
            else:
                decision = PermissionDecision(
                    level=PermissionLevel.DENY,
                    tool=tool, command=command,
                    matched_rule=None,
                    source="mode:plan",
                    reason=f"plan 模式禁止写操作: {tool}({command})",
                )
            self._log_decision(decision)
            return decision

        # 会话级覆盖（最高优先级）
        session_result = self.session.check(tool, command)
        if session_result is not None:
            decision = PermissionDecision(
                level=session_result,
                tool=tool, command=command,
                matched_rule="session_override",
                source="session",
                reason=f"会话级覆盖: {session_result.value}",
            )
            self._record_result(decision)
            self._log_decision(decision)
            return decision

        # auto 模式：AI 分类器
        if self.mode == PermissionMode.AUTO:
            decision = self._auto_classify(tool, command)
            self._record_result(decision)
            self._log_decision(decision)
            return decision

        # default 模式：按规则匹配（优先级：deny > ask > allow）
        decision = self._match_rules(tool, command)
        self._record_result(decision)
        self._log_decision(decision)
        return decision

    def _is_readonly(self, tool: str, command: str) -> bool:
        """判断是否为只读操作"""
        if tool == "read":
            return True
        if tool in self.READONLY_TOOLS:
            return True
        if tool == "bash":
            for pattern in self.READONLY_BASH_PATTERNS:
                if fnmatch.fnmatch(command, pattern):
                    return True
        return False

    def _auto_classify(self, tool: str, command: str) -> PermissionDecision:
        """
        auto 模式：基于规则分类器自动决策

        先检查 deny 列表，再检查 allow 列表，未匹配则 ask
        """
        # 检查自动拒绝
        for pattern in self.AUTO_DENY_PATTERNS:
            if match_rule(pattern, tool, command):
                return PermissionDecision(
                    level=PermissionLevel.DENY,
                    tool=tool, command=command,
                    matched_rule=pattern,
                    source="mode:auto",
                    reason="高风险操作自动拒绝",
                )

        # 检查自动放行
        for pattern in self.AUTO_ALLOW_PATTERNS:
            if match_rule(pattern, tool, command):
                return PermissionDecision(
                    level=PermissionLevel.ALLOW,
                    tool=tool, command=command,
                    matched_rule=pattern,
                    source="mode:auto",
                    reason="低风险操作自动放行",
                )

        # 检查配置规则
        decision = self._match_rules(tool, command)
        if decision.level != PermissionLevel.ASK or decision.matched_rule:
            return decision

        # 未匹配任何规则 → ask（保守策略）
        return PermissionDecision(
            level=PermissionLevel.ASK,
            tool=tool, command=command,
            matched_rule=None,
            source="mode:auto",
            reason="未匹配已知规则，需要确认",
        )

    def _match_rules(self, tool: str, command: str) -> PermissionDecision:
        """
        按优先级匹配规则：deny > ask > allow

        优先级保证：即使 allow 和 deny 都匹配，deny 优先
        """
        # 1. deny（最高优先级）
        for pattern, source in self._rules[PermissionLevel.DENY]:
            if match_rule(pattern, tool, command):
                return PermissionDecision(
                    level=PermissionLevel.DENY,
                    tool=tool, command=command,
                    matched_rule=pattern,
                    source=source,
                    reason="匹配 deny 规则",
                )

        # 2. ask
        for pattern, source in self._rules[PermissionLevel.ASK]:
            if match_rule(pattern, tool, command):
                return PermissionDecision(
                    level=PermissionLevel.ASK,
                    tool=tool, command=command,
                    matched_rule=pattern,
                    source=source,
                    reason="匹配 ask 规则，需要确认",
                )

        # 3. allow
        for pattern, source in self._rules[PermissionLevel.ALLOW]:
            if match_rule(pattern, tool, command):
                return PermissionDecision(
                    level=PermissionLevel.ALLOW,
                    tool=tool, command=command,
                    matched_rule=pattern,
                    source=source,
                    reason="匹配 allow 规则",
                )

        # 4. 无匹配规则：保守策略 → ask
        return PermissionDecision(
            level=PermissionLevel.ASK,
            tool=tool, command=command,
            matched_rule=None,
            source="default",
            reason="无匹配规则，保守策略需要确认",
        )

    def _record_result(self, decision: PermissionDecision) -> None:
        """记录决策结果到死循环防护"""
        if decision.level == PermissionLevel.DENY:
            self.cooldown.record_deny(decision.tool)
        elif decision.level == PermissionLevel.ALLOW:
            self.cooldown.record_allow(decision.tool)

    def _log_decision(self, decision: PermissionDecision) -> None:
        """记录决策日志"""
        self._decision_log.append(decision)
        if decision.level != PermissionLevel.ALLOW:
            logger.info(f"Permission check: {decision}")

    def allow_session(self, pattern: str) -> None:
        """添加会话级允许规则"""
        self.session.allow(pattern)

    def deny_session(self, pattern: str) -> None:
        """添加会话级拒绝规则"""
        self.session.deny(pattern)

    def get_decision_log(self, last_n: int = 20) -> List[PermissionDecision]:
        """获取最近的决策日志"""
        return self._decision_log[-last_n:]

    def get_stats(self) -> dict:
        """获取权限统计"""
        total = len(self._decision_log)
        allowed = sum(1 for d in self._decision_log if d.is_allowed)
        asked = sum(1 for d in self._decision_log if d.needs_confirmation)
        denied = sum(1 for d in self._decision_log if d.is_denied)

        return {
            "mode": self.mode.value,
            "total_checks": total,
            "allowed": allowed,
            "asked": asked,
            "denied": denied,
            "cooldown_tools": list(self.cooldown.consecutive_denies.keys()),
        }

    def set_mode(self, mode: str) -> None:
        """切换权限模式"""
        self.mode = PermissionMode(mode)
        logger.info(f"Permission mode changed to: {self.mode.value}")

    @property
    def current_mode(self) -> str:
        """当前权限模式"""
        return self.mode.value


# ═══════════════════════════════════════════════════════════════
# 交互式确认
# ═══════════════════════════════════════════════════════════════

def confirm_action(decision: PermissionDecision) -> bool:
    """
    交互式确认操作

    Returns:
        True = 允许，False = 拒绝
    """
    print(f"\n⚠️  权限确认: {decision.tool}({decision.command})")
    print(f"   原因: {decision.reason}")
    print(f"   规则来源: {decision.source}")
    print()
    print("  [y] 允许本次")
    print("  [a] 允许本次会话中所有同类操作")
    print("  [n] 拒绝")
    print("  [d] 拒绝并在本次会话中禁止同类操作")
    print()

    try:
        choice = input("  选择 [y/a/n/d]: ").strip().lower()
    except (EOFError, KeyboardInterrupt):
        return False

    if choice == "y":
        return True
    elif choice == "a":
        # 允许本次会话中所有同类操作 — 由调用方处理
        return True
    elif choice == "d":
        return False
    else:
        return False


def confirm_action_with_session(decision: PermissionDecision,
                                pm: PermissionManager) -> bool:
    """
    交互式确认操作（含会话级覆盖处理）

    Returns:
        True = 允许，False = 拒绝
    """
    print(f"\n⚠️  权限确认: {decision.tool}({decision.command})")
    print(f"   原因: {decision.reason}")
    print(f"   规则来源: {decision.source}")
    print()
    print("  [y] 允许本次")
    print("  [a] 允许本次会话中所有同类操作")
    print("  [n] 拒绝")
    print("  [d] 拒绝并在本次会话中禁止同类操作")
    print()

    try:
        choice = input("  选择 [y/a/n/d]: ").strip().lower()
    except (EOFError, KeyboardInterrupt):
        return False

    if choice == "y":
        return True
    elif choice == "a":
        # 添加会话级允许规则
        pattern = f"{decision.tool}({decision.command[:decision.command.find(' ')] + '*' if ' ' in decision.command else '*'})"
        pm.allow_session(pattern)
        print(f"   ✅ 已添加会话允许规则: {pattern}")
        return True
    elif choice == "d":
        pattern = f"{decision.tool}({decision.command[:decision.command.find(' ')] + '*' if ' ' in decision.command else '*'})"
        pm.deny_session(pattern)
        print(f"   🚫 已添加会话拒绝规则: {pattern}")
        return False
    else:
        return False


# ═══════════════════════════════════════════════════════════════
# 工具函数
# ═══════════════════════════════════════════════════════════════

def parse_tool_command(raw_command: str) -> Tuple[str, str]:
    """
    解析工具名和命令内容

    格式:
    - "bash: remove -rf /path" → ("bash", "remove -rf /path")
    - "read: /etc/passwd" → ("read", "/etc/passwd")
    - "write: ./src/main.py" → ("write", "./src/main.py")
    - "rm file" → ("bash", "rm file")  # 默认 bash

    Returns:
        (tool, command)
    """
    if ":" in raw_command:
        tool, command = raw_command.split(":", 1)
        tool = tool.strip()
        command = command.strip()
        return tool, command
    else:
        return "bash", raw_command.strip()


def create_permission_manager(project_root: str = ".",
                              mode: str = "default") -> PermissionManager:
    """便捷函数：创建权限管理器"""
    return PermissionManager(project_root=project_root, mode=mode)
