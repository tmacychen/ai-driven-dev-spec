#!/usr/bin/env python3
"""
P0-4 单元测试：权限管理器

测试覆盖：
- PermissionLevel / PermissionMode 枚举
- PermissionDecision 数据类
- match_rule 规则匹配
- CooldownState 死循环防护
- SessionOverrides 会话级覆盖
- PermissionManager 核心逻辑
  - default 模式：按规则匹配
  - plan 模式：只读放行
  - auto 模式：AI 分类器
  - bypass 模式：全部放行
- parse_tool_command 工具命令解析
- 交互式确认
"""

import json
import tempfile
import time
import shutil
import unittest
from pathlib import Path

from permission_manager import (
    PermissionLevel, PermissionMode, PermissionDecision,
    match_rule, CooldownState, SessionOverrides, PermissionManager,
    parse_tool_command, create_permission_manager,
)


class TestPermissionLevel(unittest.TestCase):
    """权限级别枚举测试"""

    def test_allow_value(self):
        self.assertEqual(PermissionLevel.ALLOW.value, "allow")

    def test_ask_value(self):
        self.assertEqual(PermissionLevel.ASK.value, "ask")

    def test_deny_value(self):
        self.assertEqual(PermissionLevel.DENY.value, "deny")


class TestPermissionMode(unittest.TestCase):
    """权限模式枚举测试"""

    def test_default_value(self):
        self.assertEqual(PermissionMode.DEFAULT.value, "default")

    def test_plan_value(self):
        self.assertEqual(PermissionMode.PLAN.value, "plan")

    def test_auto_value(self):
        self.assertEqual(PermissionMode.AUTO.value, "auto")

    def test_bypass_value(self):
        self.assertEqual(PermissionMode.BYPASS.value, "bypass")


class TestPermissionDecision(unittest.TestCase):
    """权限决策结果测试"""

    def test_is_allowed(self):
        d = PermissionDecision(level=PermissionLevel.ALLOW, tool="bash",
                               command="ls", matched_rule="bash(ls*)", source="default")
        self.assertTrue(d.is_allowed)
        self.assertFalse(d.needs_confirmation)
        self.assertFalse(d.is_denied)

    def test_needs_confirmation(self):
        d = PermissionDecision(level=PermissionLevel.ASK, tool="bash",
                               command="rm -r /tmp", matched_rule="bash(rm*)", source="default")
        self.assertFalse(d.is_allowed)
        self.assertTrue(d.needs_confirmation)
        self.assertFalse(d.is_denied)

    def test_is_denied(self):
        d = PermissionDecision(level=PermissionLevel.DENY, tool="bash",
                               command="sudo rm", matched_rule="bash(sudo*)", source="default")
        self.assertFalse(d.is_allowed)
        self.assertFalse(d.needs_confirmation)
        self.assertTrue(d.is_denied)

    def test_str_format(self):
        d = PermissionDecision(level=PermissionLevel.DENY, tool="bash",
                               command="sudo rm", matched_rule="bash(sudo*)",
                               source="default", reason="匹配 deny 规则")
        s = str(d)
        self.assertIn("DENY", s)
        self.assertIn("bash", s)
        self.assertIn("sudo rm", s)


class TestMatchRule(unittest.TestCase):
    """权限规则匹配测试"""

    def test_exact_tool_match(self):
        self.assertTrue(match_rule("bash(ls*)", "bash", "ls -la"))

    def test_tool_mismatch(self):
        self.assertFalse(match_rule("bash(ls*)", "read", "ls -la"))

    def test_wildcard_command(self):
        self.assertTrue(match_rule("read(*)", "read", "/etc/passwd"))
        self.assertTrue(match_rule("read(*)", "read", "any file"))

    def test_prefix_wildcard(self):
        self.assertTrue(match_rule("bash(rm*)", "bash", "rm -r /tmp"))
        self.assertTrue(match_rule("bash(rm*)", "bash", "rm"))

    def test_path_wildcard(self):
        self.assertTrue(match_rule("write(./*)", "write", "./src/main.py"))
        self.assertFalse(match_rule("write(./*)", "write", "/etc/passwd"))

    def test_no_paren_pattern(self):
        self.assertTrue(match_rule("read", "read", "anything"))

    def test_complex_pattern(self):
        self.assertTrue(match_rule("bash(git status*)", "bash", "git status --short"))
        self.assertFalse(match_rule("bash(git status*)", "bash", "git push"))


class TestCooldownState(unittest.TestCase):
    """死循环防护测试"""

    def setUp(self):
        self.cd = CooldownState(max_consecutive=3, cooldown_seconds=1.0)

    def test_no_cooldown_initially(self):
        self.assertFalse(self.cd.is_in_cooldown("bash"))

    def test_record_deny_increments(self):
        self.cd.record_deny("bash")
        self.assertEqual(self.cd.consecutive_denies.get("bash"), 1)
        self.assertFalse(self.cd.is_in_cooldown("bash"))

    def test_cooldown_triggered(self):
        for _ in range(3):
            self.cd.record_deny("bash")
        self.assertTrue(self.cd.is_in_cooldown("bash"))

    def test_record_allow_resets(self):
        for _ in range(2):
            self.cd.record_deny("bash")
        self.cd.record_allow("bash")
        self.assertNotIn("bash", self.cd.consecutive_denies)

    def test_cooldown_expires(self):
        cd = CooldownState(max_consecutive=2, cooldown_seconds=0.1)
        cd.record_deny("bash")
        cd.record_deny("bash")
        self.assertTrue(cd.is_in_cooldown("bash"))
        time.sleep(0.15)
        self.assertFalse(cd.is_in_cooldown("bash"))

    def test_cooldown_remaining(self):
        cd = CooldownState(max_consecutive=2, cooldown_seconds=1.0)
        cd.record_deny("bash")
        cd.record_deny("bash")
        remaining = cd.cooldown_remaining("bash")
        self.assertGreater(remaining, 0)
        self.assertLessEqual(remaining, 1.0)

    def test_different_tools_independent(self):
        for _ in range(3):
            self.cd.record_deny("bash")
        self.assertTrue(self.cd.is_in_cooldown("bash"))
        self.assertFalse(self.cd.is_in_cooldown("read"))


class TestSessionOverrides(unittest.TestCase):
    """会话级覆盖测试"""

    def setUp(self):
        self.so = SessionOverrides()

    def test_no_override_initially(self):
        self.assertIsNone(self.so.check("bash", "ls"))

    def test_allow_override(self):
        self.so.allow("bash(rm*)")
        self.assertEqual(self.so.check("bash", "rm -r /tmp"), PermissionLevel.ALLOW)

    def test_deny_override(self):
        self.so.deny("bash(ls*)")
        self.assertEqual(self.so.check("bash", "ls -la"), PermissionLevel.DENY)

    def test_deny_priority_over_allow(self):
        self.so.allow("bash(rm*)")
        self.so.deny("bash(rm*)")
        # deny 先检查
        self.assertEqual(self.so.check("bash", "rm -r /tmp"), PermissionLevel.DENY)

    def test_non_matching_override(self):
        self.so.allow("bash(ls*)")
        self.assertIsNone(self.so.check("bash", "rm -r /tmp"))


class TestPermissionManagerDefault(unittest.TestCase):
    """权限管理器 - default 模式测试"""

    def setUp(self):
        self.tmp = tempfile.mkdtemp(prefix="adds_test_perm_")
        self.pm = PermissionManager(project_root=self.tmp, mode="default")

    def tearDown(self):
        shutil.rmtree(self.tmp)

    def test_allow_ls(self):
        d = self.pm.check("bash", "ls -la")
        self.assertTrue(d.is_allowed)

    def test_allow_read(self):
        d = self.pm.check("read", "./src/main.py")
        self.assertTrue(d.is_allowed)

    def test_allow_write_project(self):
        d = self.pm.check("write", "./src/main.py")
        self.assertTrue(d.is_allowed)

    def test_ask_rm(self):
        d = self.pm.check("bash", "rm -r /tmp/test")
        self.assertTrue(d.needs_confirmation)

    def test_ask_git_push(self):
        d = self.pm.check("bash", "git push origin main")
        self.assertTrue(d.needs_confirmation)

    def test_deny_sudo(self):
        d = self.pm.check("bash", "sudo apt install")
        self.assertTrue(d.is_denied)

    def test_deny_disk_format(self):
        d = self.pm.check("bash", "dd if=/dev/zero of=/dev/sda")
        self.assertTrue(d.is_denied)

    def test_deny_write_system(self):
        d = self.pm.check("write", "/etc/passwd")
        self.assertTrue(d.is_denied)

    def test_deny_priority_over_allow(self):
        # deny 规则优先于 allow
        d = self.pm.check("bash", "sudo ls")
        self.assertTrue(d.is_denied)

    def test_unknown_command_ask(self):
        # 无匹配规则 → 保守策略 ask
        d = self.pm.check("custom_tool", "some_action")
        self.assertTrue(d.needs_confirmation)

    def test_decision_log(self):
        self.pm.check("bash", "ls")
        self.pm.check("bash", "sudo rm")
        log = self.pm.get_decision_log()
        self.assertEqual(len(log), 2)

    def test_stats(self):
        self.pm.check("bash", "ls")
        self.pm.check("bash", "rm test")
        self.pm.check("bash", "sudo ls")
        stats = self.pm.get_stats()
        self.assertEqual(stats["total_checks"], 3)
        self.assertEqual(stats["mode"], "default")


class TestPermissionManagerPlan(unittest.TestCase):
    """权限管理器 - plan 模式测试"""

    def setUp(self):
        self.tmp = tempfile.mkdtemp(prefix="adds_test_perm_plan_")
        self.pm = PermissionManager(project_root=self.tmp, mode="plan")

    def tearDown(self):
        shutil.rmtree(self.tmp)

    def test_allow_read_commands(self):
        self.assertTrue(self.pm.check("read", "./src/main.py").is_allowed)

    def test_allow_bash_ls(self):
        self.assertTrue(self.pm.check("bash", "ls -la").is_allowed)

    def test_allow_bash_git_status(self):
        self.assertTrue(self.pm.check("bash", "git status").is_allowed)

    def test_deny_write(self):
        self.assertTrue(self.pm.check("write", "./src/main.py").is_denied)

    def test_deny_rm(self):
        self.assertTrue(self.pm.check("bash", "rm -r /tmp").is_denied)

    def test_deny_git_commit(self):
        self.assertTrue(self.pm.check("bash", "git commit -m 'test'").is_denied)


class TestPermissionManagerAuto(unittest.TestCase):
    """权限管理器 - auto 模式测试"""

    def setUp(self):
        self.tmp = tempfile.mkdtemp(prefix="adds_test_perm_auto_")
        self.pm = PermissionManager(project_root=self.tmp, mode="auto")

    def tearDown(self):
        shutil.rmtree(self.tmp)

    def test_auto_allow_ls(self):
        d = self.pm.check("bash", "ls -la")
        self.assertTrue(d.is_allowed)

    def test_auto_deny_sudo(self):
        d = self.pm.check("bash", "sudo apt install")
        self.assertTrue(d.is_denied)

    def test_auto_unknown_ask(self):
        # 未匹配 → ask
        d = self.pm.check("custom", "unknown_action")
        self.assertTrue(d.needs_confirmation)


class TestPermissionManagerBypass(unittest.TestCase):
    """权限管理器 - bypass 模式测试"""

    def setUp(self):
        self.tmp = tempfile.mkdtemp(prefix="adds_test_perm_bypass_")
        self.pm = PermissionManager(project_root=self.tmp, mode="bypass")

    def tearDown(self):
        shutil.rmtree(self.tmp)

    def test_bypass_allow_all(self):
        self.assertTrue(self.pm.check("bash", "sudo rm -r /dangerous").is_allowed)
        self.assertTrue(self.pm.check("write", "/etc/passwd").is_allowed)
        self.assertTrue(self.pm.check("bash", "ls").is_allowed)

    def test_bypass_reason(self):
        d = self.pm.check("bash", "sudo rm -r /dangerous")
        self.assertIn("bypass", d.reason)


class TestPermissionManagerCooldown(unittest.TestCase):
    """权限管理器 - 死循环防护测试"""

    def setUp(self):
        self.tmp = tempfile.mkdtemp(prefix="adds_test_perm_cd_")
        self.pm = PermissionManager(project_root=self.tmp, mode="default")
        self.pm.cooldown = CooldownState(max_consecutive=3, cooldown_seconds=1.0)

    def tearDown(self):
        shutil.rmtree(self.tmp)

    def test_cooldown_after_repeated_deny(self):
        # 连续 deny 3 次
        for _ in range(3):
            self.pm.check("bash", "sudo ls")
        # 第4次应该触发冷却
        d = self.pm.check("bash", "sudo ls")
        self.assertTrue(d.is_denied)
        self.assertEqual(d.source, "cooldown")

    def test_cooldown_allows_other_tools(self):
        for _ in range(3):
            self.pm.check("bash", "sudo ls")
        # read 工具不受影响
        d = self.pm.check("read", "./file.py")
        self.assertTrue(d.is_allowed)


class TestPermissionManagerSessionOverrides(unittest.TestCase):
    """权限管理器 - 会话级覆盖测试"""

    def setUp(self):
        self.tmp = tempfile.mkdtemp(prefix="adds_test_perm_so_")
        self.pm = PermissionManager(project_root=self.tmp, mode="default")

    def tearDown(self):
        shutil.rmtree(self.tmp)

    def test_session_allow_overrides_ask(self):
        # rm 默认是 ask，会话覆盖后变为 allow
        self.pm.allow_session("bash(rm*)")
        d = self.pm.check("bash", "rm -r /tmp")
        self.assertTrue(d.is_allowed)
        self.assertEqual(d.source, "session")

    def test_session_deny_overrides_allow(self):
        # ls 默认是 allow，会话覆盖后变为 deny
        self.pm.deny_session("bash(ls*)")
        d = self.pm.check("bash", "ls -la")
        self.assertTrue(d.is_denied)
        self.assertEqual(d.source, "session")


class TestPermissionManagerSetMode(unittest.TestCase):
    """权限管理器 - 模式切换测试"""

    def setUp(self):
        self.tmp = tempfile.mkdtemp(prefix="adds_test_perm_sm_")
        self.pm = PermissionManager(project_root=self.tmp, mode="default")

    def tearDown(self):
        shutil.rmtree(self.tmp)

    def test_set_mode_plan(self):
        self.pm.set_mode("plan")
        self.assertEqual(self.pm.current_mode, "plan")
        # plan 模式下写操作被拒
        self.assertTrue(self.pm.check("write", "./file.py").is_denied)

    def test_set_mode_bypass(self):
        self.pm.set_mode("bypass")
        self.assertEqual(self.pm.current_mode, "bypass")
        self.assertTrue(self.pm.check("bash", "sudo rm").is_allowed)

    def test_set_mode_default(self):
        self.pm.set_mode("bypass")
        self.pm.set_mode("default")
        self.assertEqual(self.pm.current_mode, "default")
        self.assertTrue(self.pm.check("bash", "sudo rm").is_denied)


class TestPermissionManagerWithSettingsFile(unittest.TestCase):
    """权限管理器 - 从配置文件加载测试"""

    def setUp(self):
        self.tmp = tempfile.mkdtemp(prefix="adds_test_perm_sf_")
        ai_dir = Path(self.tmp) / ".ai"
        ai_dir.mkdir()
        settings = {
            "permissions": {
                "mode": "default",
                "rules": {
                    "allow": ["bash(hello*)", "read(*)"],
                    "ask": ["bash(deploy*)"],
                    "deny": ["bash(destroy*)"]
                }
            }
        }
        (ai_dir / "settings.json").write_text(json.dumps(settings), encoding="utf-8")

    def tearDown(self):
        shutil.rmtree(self.tmp)

    def test_load_from_settings(self):
        pm = PermissionManager(project_root=self.tmp, mode="default")
        # 自定义规则
        self.assertTrue(pm.check("bash", "hello world").is_allowed)
        self.assertTrue(pm.check("bash", "deploy production").needs_confirmation)
        self.assertTrue(pm.check("bash", "destroy all").is_denied)

    def test_default_rules_not_used_when_settings_exist(self):
        pm = PermissionManager(project_root=self.tmp, mode="default")
        # ls 不在自定义 allow 中，应走 default fallback
        d = pm.check("bash", "ls -la")
        # 没有匹配任何规则 → ask（保守策略）
        self.assertTrue(d.needs_confirmation)


class TestParseToolCommand(unittest.TestCase):
    """工具命令解析测试"""

    def test_bash_prefix(self):
        tool, cmd = parse_tool_command("bash: rm -r /tmp")
        self.assertEqual(tool, "bash")
        self.assertEqual(cmd, "rm -r /tmp")

    def test_read_prefix(self):
        tool, cmd = parse_tool_command("read: /etc/passwd")
        self.assertEqual(tool, "read")
        self.assertEqual(cmd, "/etc/passwd")

    def test_write_prefix(self):
        tool, cmd = parse_tool_command("write: ./src/main.py")
        self.assertEqual(tool, "write")
        self.assertEqual(cmd, "./src/main.py")

    def test_no_prefix_defaults_bash(self):
        tool, cmd = parse_tool_command("rm -r /tmp")
        self.assertEqual(tool, "bash")
        self.assertEqual(cmd, "rm -r /tmp")

    def test_empty_command(self):
        tool, cmd = parse_tool_command("")
        self.assertEqual(tool, "bash")
        self.assertEqual(cmd, "")


class TestCreatePermissionManager(unittest.TestCase):
    """便捷函数测试"""

    def test_create_default(self):
        pm = create_permission_manager()
        self.assertEqual(pm.mode, PermissionMode.DEFAULT)

    def test_create_with_mode(self):
        pm = create_permission_manager(mode="plan")
        self.assertEqual(pm.mode, PermissionMode.PLAN)


if __name__ == "__main__":
    unittest.main()
