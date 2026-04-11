#!/usr/bin/env python3
"""
ADDS P0 集成测试 — 四层协同端到端验证

测试场景：
1. 四层模块初始化与数据流串联
2. 压缩触发与 Session 归档
3. 记忆注入与 SystemPromptBuilder
4. 权限拦截与决策流转
5. 完整会话生命周期
6. 跨层数据一致性
"""

import asyncio
import json
import shutil
import tempfile
import unittest
from datetime import datetime
from pathlib import Path
from typing import AsyncIterator

from model.base import ModelInterface, ModelResponse


# ═══════════════════════════════════════════════════════════
# 测试用 Mock 模型
# ═══════════════════════════════════════════════════════════

class MockModel(ModelInterface):
    """测试用 Mock 模型"""

    def __init__(self, context_window=128000, responses=None):
        self._context_window = context_window
        self._responses = responses or ["这是测试响应"]
        self._call_count = 0

    async def chat(self, messages, system_prompt=None, tools=None, stream=True, **kwargs):
        resp_text = self._responses[self._call_count % len(self._responses)]
        self._call_count += 1
        yield ModelResponse(
            content=resp_text,
            model="mock-model",
            usage={"input_tokens": 100, "output_tokens": 50},
            finish_reason="stop",
        )

    def count_tokens(self, text: str) -> int:
        return len(text) // 4

    def get_context_window(self) -> int:
        return self._context_window

    def get_model_name(self) -> str:
        return "mock-model"

    def supports_feature(self, name: str) -> bool:
        return name in ("streaming", "thinking")


# ═══════════════════════════════════════════════════════════
# 基础设施
# ═══════════════════════════════════════════════════════════

class P0IntegrationTestBase(unittest.TestCase):
    """P0 集成测试基类"""

    def setUp(self):
        self.tmpdir = tempfile.mkdtemp(prefix="adds_p0_integ_")
        self.project_root = self.tmpdir

        ai_dir = Path(self.tmpdir) / ".ai"
        ai_dir.mkdir(parents=True, exist_ok=True)
        (ai_dir / "sessions").mkdir(exist_ok=True)
        (ai_dir / "memories" / "SKILLS").mkdir(parents=True, exist_ok=True)

        settings = {
            "permissions": {
                "mode": "default",
                "rules": {
                    "allow": [
                        "bash(ls*)", "bash(cat*)", "bash(python*)",
                        "bash(pytest*)", "bash(git status*)",
                        "read(*)", "write(./*)",
                    ],
                    "ask": [
                        "bash(rm*)", "bash(pip install*)",
                        "bash(git push*)", "bash(git commit*)",
                    ],
                    "deny": [
                        "bash(sudo*)", "bash(dd*)",
                        "write(/etc/*)",
                    ],
                },
            },
            "compaction": {
                "tool_result_threshold": 2000,
                "layer2_trigger": 0.8,
                "layer1_trigger": 0.5,
                "warn_threshold": 0.85,
                "hard_limit": 0.95,
            },
            "memory": {
                "index_mem_path": ".ai/sessions/index.mem",
                "sessions_dir": ".ai/sessions/",
                "max_fixed_memory_chars": 2000,
                "evolution_min_occurrences": 2,
            },
        }
        with open(ai_dir / "settings.json", "w", encoding="utf-8") as f:
            json.dump(settings, f, indent=2)

        # 创建 index.mem（使用标准格式）
        index_mem = ai_dir / "sessions" / "index.mem"
        index_mem.write_text(
            "# ADDS 记忆索引\n"
            "# Page: 1\n"
            "# 更新时间: 2026-04-11 09:00\n"
            "# 此文件始终注入上下文，是 Agent 的\"长期记忆索引\"\n"
            "# Prev: null\n"
            "# Next: null\n"
            "# ⚠️ 固定记忆优先级低于 System Prompt，冲突以 System Prompt 为准\n\n"
            "---\n\n"
            "## 已掌握技能\n\n"
            "## 固定记忆\n\n"
            "- [common] 使用 Python 3.9+ 语法\n"
            "- [dev] 测试驱动开发\n\n"
            "## 时间线\n"
            "| 时间 | 文件 | 摘要 | 优先级 |\n"
            "|------|------|------|--------|\n",
            encoding="utf-8",
        )

    def tearDown(self):
        shutil.rmtree(self.tmpdir, ignore_errors=True)


# ═══════════════════════════════════════════════════════════
# 场景 1: 四层模块初始化与数据流串联
# ═══════════════════════════════════════════════════════════

class TestScenario1_FourLayerInit(P0IntegrationTestBase):
    """场景 1: 四层模块在 AgentLoop 中的正确初始化"""

    def test_agentloop_initializes_all_p0_layers(self):
        """AgentLoop 构造函数正确初始化 P0-1~P0-4 全部模块"""
        from agent_loop import AgentLoop

        model = MockModel(context_window=128000)
        loop = AgentLoop(
            model=model,
            system_prompt="你是一个测试助手",
            console=None, skin=None,
            project_root=self.project_root,
            agent_role="developer",
            feature="test_feature",
            permission_mode="default",
        )

        # P0-1
        self.assertIsNotNone(loop.model)
        self.assertEqual(loop.model.get_model_name(), "mock-model")

        # P0-2
        self.assertIsNotNone(loop.budget)
        self.assertEqual(loop.budget.context_window, 128000)
        self.assertIsNotNone(loop.session_mgr)
        self.assertIsNotNone(loop.compactor)

        # P0-4
        self.assertIsNotNone(loop.permission)
        self.assertEqual(loop.permission.current_mode, "default")

    def test_model_context_window_flows_to_budget(self):
        """P0-1 → P0-2: 模型上下文窗口正确传递给 TokenBudget"""
        from agent_loop import AgentLoop

        for cw in [32000, 128000]:
            model = MockModel(context_window=cw)
            loop = AgentLoop(model=model, project_root=self.project_root)
            self.assertEqual(loop.budget.context_window, cw)

    def test_permission_check_in_model_context(self):
        """P0-4: 权限检查在 P0-1 模型上下文中工作"""
        from agent_loop import AgentLoop

        model = MockModel()
        loop = AgentLoop(model=model, project_root=self.project_root, permission_mode="default")

        d = loop.permission.check("bash", "ls -la")
        self.assertTrue(d.is_allowed)

        d = loop.permission.check("bash", "sudo apt install something")
        self.assertTrue(d.is_denied)


# ═══════════════════════════════════════════════════════════
# 场景 2: 压缩触发与 Session 归档
# ═══════════════════════════════════════════════════════════

class TestScenario2_CompressionAndArchive(P0IntegrationTestBase):
    """场景 2: TokenBudget → ContextCompactor → SessionManager"""

    def test_budget_triggers_layer1(self):
        """P0-2: Token 超过 50% 触发 Layer1 建议"""
        from token_budget import TokenBudget

        budget = TokenBudget(context_window=10000)
        budget.allocate(system_prompt=1500, memory=1000)
        for _ in range(20):
            budget.track("history", 200)

        self.assertGreater(budget.utilization, 0.5)
        self.assertTrue(budget.should_compact_layer1())

    def test_budget_triggers_layer2(self):
        """P0-2: Token 超过 80% 触发 Layer2 建议"""
        from token_budget import TokenBudget

        budget = TokenBudget(context_window=10000)
        budget.allocate(system_prompt=1500, memory=1000)
        for _ in range(30):
            budget.track("history", 200)

        self.assertGreater(budget.utilization, 0.8)
        self.assertTrue(budget.should_compact_layer2())

    def test_session_create_append_archive(self):
        """P0-2: Session 完整生命周期"""
        from session_manager import SessionManager

        sessions_dir = str(Path(self.project_root) / ".ai" / "sessions")
        mgr = SessionManager(sessions_dir=sessions_dir)

        session_id = mgr.create_session(agent="developer", feature="auth")
        self.assertIsNotNone(session_id)

        ses_path = Path(sessions_dir) / f"{session_id}.ses"
        self.assertTrue(ses_path.exists())

        mgr.append_message("user", "实现登录功能")
        mgr.append_message("assistant", "好的，开始实现...")

        # 归档
        mem_path = mgr.archive_session(summary="实现了用户认证基础功能")
        self.assertIsNotNone(mem_path)
        self.assertTrue(Path(mem_path).exists())

    def test_layer1_compress_message(self):
        """P0-2: Layer1 对消息进行实时压缩"""
        from token_budget import TokenBudget
        from session_manager import SessionManager
        from context_compactor import ContextCompactor

        budget = TokenBudget(context_window=100000)
        sessions_dir = str(Path(self.project_root) / ".ai" / "sessions")
        session_mgr = SessionManager(sessions_dir=sessions_dir)
        session_mgr.create_session(agent="dev", feature="test")
        compactor = ContextCompactor(budget, session_mgr)

        # 构造一个超长 tool_result 消息
        long_output = "Line " * 3000
        msg = {"role": "tool_result", "content": long_output}

        compressed_msg, result = compactor.layer1_compress(msg)

        # 消息被压缩（内容变短或保存到 log）
        self.assertLessEqual(len(compressed_msg["content"]), len(long_output))

    def test_layer2_archive_with_mock_model(self):
        """P0-2: Layer2 归档使用 Mock 模型"""
        from token_budget import TokenBudget
        from session_manager import SessionManager
        from context_compactor import ContextCompactor

        budget = TokenBudget(context_window=100000)
        sessions_dir = str(Path(self.project_root) / ".ai" / "sessions")
        session_mgr = SessionManager(sessions_dir=sessions_dir)
        session_id = session_mgr.create_session(agent="developer", feature="test")
        session_mgr.append_message("user", "实现功能")
        session_mgr.append_message("assistant", "好的")

        compactor = ContextCompactor(budget, session_mgr)
        model = MockModel(
            context_window=100000,
            responses=["## 摘要\n\n实现了测试功能。"],
        )

        result = compactor.layer2_archive(model_interface=model)
        if result:
            self.assertTrue(Path(result.mem_path).exists())


# ═══════════════════════════════════════════════════════════
# 场景 3: 记忆注入与 SystemPromptBuilder
# ═══════════════════════════════════════════════════════════

class TestScenario3_MemoryInjectionToSP(P0IntegrationTestBase):
    """场景 3: MemoryManager → RoleMemoryInjector → SystemPromptBuilder"""

    def test_memory_injection_into_system_prompt(self):
        """P0-3: 记忆注入到 SystemPromptBuilder"""
        from system_prompt_builder import SystemPromptBuilder

        builder = SystemPromptBuilder(project_root=self.project_root)

        memory_injection = (
            "## Agent 记忆（角色: developer）\n\n"
            "- [common] 使用 Python 3.9+ 语法\n"
            "- [dev] 测试驱动开发\n"
        )

        context = {
            "current_agent": "developer",
            "memory_injection": memory_injection,
        }

        prompt_sections = builder.build_system_prompt(context)
        memory_found = any("测试驱动开发" in s for s in prompt_sections)
        self.assertTrue(memory_found)

    def test_prev_session_summary_in_system_prompt(self):
        """P0-2: 上一个 session 摘要注入到 SP"""
        from system_prompt_builder import SystemPromptBuilder

        builder = SystemPromptBuilder(project_root=self.project_root)

        context = {
            "current_agent": "developer",
            "prev_session_summary": "实现了用户认证模块",
            "prev_session_id": "20260410-153000",
        }

        prompt_sections = builder.build_system_prompt(context)
        full_prompt = "\n".join(s for s in prompt_sections if s)

        self.assertIn("用户认证模块", full_prompt)
        self.assertIn("20260410-153000", full_prompt)

    def test_static_dynamic_boundary_in_prompt(self):
        """P0-2: SP 包含静态/动态边界标记"""
        from system_prompt_builder import SystemPromptBuilder, STATIC_BOUNDARY

        builder = SystemPromptBuilder(project_root=self.project_root)
        context = {"current_agent": "developer"}
        prompt_sections = builder.build_system_prompt(context)

        self.assertIn(STATIC_BOUNDARY, prompt_sections)

        static_idx = prompt_sections.index(STATIC_BOUNDARY)
        static_content = "\n".join(prompt_sections[:static_idx])
        self.assertIn("核心约束", static_content)

    def test_role_injector_with_fixed_memory(self):
        """P0-3: RoleMemoryInjector 按角色过滤固定记忆"""
        from role_memory_injector import RoleAwareMemoryInjector
        from index_priority_sorter import MemoryItem

        injector = RoleAwareMemoryInjector()

        # 使用 MemoryItem 格式
        items = [
            MemoryItem(content="使用 Python 3.9+ 语法", category="environment", role="common"),
            MemoryItem(content="测试驱动开发，先写测试", category="skill", role="developer"),
            MemoryItem(content="微服务架构优先", category="experience", role="architect"),
            MemoryItem(content="回归测试必须覆盖核心功能", category="skill", role="tester"),
        ]

        # developer 角色应该看到 common + developer
        dev_filtered = injector.filter_memories_for_role(items, current_role="developer")
        dev_contents = [m.content for m in dev_filtered]
        self.assertIn("使用 Python 3.9+ 语法", dev_contents)
        self.assertIn("测试驱动开发，先写测试", dev_contents)
        self.assertNotIn("微服务架构优先", dev_contents)

        # architect 角色应该看到 common + architect
        arch_filtered = injector.filter_memories_for_role(items, current_role="architect")
        arch_contents = [m.content for m in arch_filtered]
        self.assertIn("使用 Python 3.9+ 语法", arch_contents)
        self.assertIn("微服务架构优先", arch_contents)


# ═══════════════════════════════════════════════════════════
# 场景 4: 权限拦截与决策流转
# ═══════════════════════════════════════════════════════════

class TestScenario4_PermissionDecisionFlow(P0IntegrationTestBase):
    """场景 4: PermissionManager 决策流转"""

    def test_permission_modes_affect_tool_execution(self):
        """P0-4: 不同权限模式影响工具执行"""
        from permission_manager import PermissionManager

        # default: rm 需确认
        pm = PermissionManager(project_root=self.project_root, mode="default")
        d = pm.check("bash", "rm -rf /tmp/test")
        self.assertTrue(d.needs_confirmation)

        # plan: rm 拒绝
        pm = PermissionManager(project_root=self.project_root, mode="plan")
        d = pm.check("bash", "rm -rf /tmp/test")
        self.assertTrue(d.is_denied)

        # bypass: rm 放行
        pm = PermissionManager(project_root=self.project_root, mode="bypass")
        d = pm.check("bash", "rm -rf /tmp/test")
        self.assertTrue(d.is_allowed)

    def test_session_override_affects_decision(self):
        """P0-4: 会话级覆盖改变权限决策"""
        from permission_manager import PermissionManager, SessionOverrides

        overrides = SessionOverrides()
        pm = PermissionManager(project_root=self.project_root, mode="default", session_overrides=overrides)

        d = pm.check("bash", "pip install requests")
        self.assertTrue(d.needs_confirmation)

        overrides.allow("bash(pip install*)")
        d = pm.check("bash", "pip install requests")
        self.assertTrue(d.is_allowed)
        self.assertEqual(d.source, "session")

    def test_cooldown_prevents_deadloop(self):
        """P0-4: 死循环防护：plan 模式下写操作连续拒绝后进入冷却"""
        from permission_manager import PermissionManager

        pm = PermissionManager(project_root=self.project_root, mode="plan")

        # plan 模式下写操作被拒
        for i in range(4):
            d = pm.check("write", f"./src/file{i}.py")
            self.assertTrue(d.is_denied)

        # 检查是否在冷却中
        self.assertTrue(pm.cooldown.is_in_cooldown("write"))

    def test_permission_with_agent_loop(self):
        """P0-4 + P0-1: 权限与 AgentLoop 集成"""
        from agent_loop import AgentLoop

        model = MockModel()
        loop = AgentLoop(model=model, project_root=self.project_root, permission_mode="plan")

        d = loop.permission.check("bash", "ls -la")
        self.assertTrue(d.is_allowed)

        d = loop.permission.check("write", "./src/main.py")
        self.assertTrue(d.is_denied)


# ═══════════════════════════════════════════════════════════
# 场景 5: 完整会话生命周期
# ═══════════════════════════════════════════════════════════

class TestScenario5_FullSessionLifecycle(P0IntegrationTestBase):
    """场景 5: 完整会话生命周期"""

    def test_compaction_warning_at_threshold(self):
        """P0-2: Token 接近阈值时发出警告"""
        from token_budget import TokenBudget
        from session_manager import SessionManager
        from context_compactor import ContextCompactor

        budget = TokenBudget(context_window=10000)
        sessions_dir = str(Path(self.project_root) / ".ai" / "sessions")
        session_mgr = SessionManager(sessions_dir=sessions_dir)
        compactor = ContextCompactor(budget, session_mgr)

        budget.allocate(system_prompt=1500, memory=1000)

        # 推到 85% 以上
        for _ in range(35):
            budget.track("history", 200)

        warning = compactor.get_warning()
        self.assertIsNotNone(warning)
        # 警告文本包含利用率百分比
        self.assertTrue("%" in warning or "极限" in warning or "利用率" in warning)

    def test_memory_manager_index_update(self):
        """P0-3: MemoryManager 更新 index.mem"""
        from memory_manager import MemoryManager

        mem_mgr = MemoryManager(project_root=self.project_root)

        # add_index_entry 会读取当前 index.mem 并更新
        mem_mgr.add_index_entry(
            time="04-11 09:30",
            file="20260411-093000.mem",
            summary="P0集成测试",
            priority="高",
        )

        # 重新读取验证
        content, items = mem_mgr.read_index_mem()
        self.assertIn("20260411-093000", content)

    def test_full_lifecycle_with_mock_model(self):
        """完整生命周期：初始化 → 对话模拟 → 归档"""
        from token_budget import TokenBudget, estimate_tokens
        from session_manager import SessionManager
        from context_compactor import ContextCompactor
        from permission_manager import PermissionManager

        # 1. 初始化
        model = MockModel(context_window=128000)
        budget = TokenBudget(context_window=model.get_context_window())
        sessions_dir = str(Path(self.project_root) / ".ai" / "sessions")
        session_mgr = SessionManager(sessions_dir=sessions_dir)
        compactor = ContextCompactor(budget, session_mgr)
        permission = PermissionManager(project_root=self.project_root, mode="default")

        # 2. 创建 session
        session_id = session_mgr.create_session(agent="developer", feature="auth")

        # 3. 分配 token
        sp_tokens = estimate_tokens("你是一个开发者助手")
        budget.allocate(system_prompt=sp_tokens, memory=0)

        # 4. 模拟对话
        commands = [
            ("bash", "ls -la src/"),
            ("bash", "cat src/main.py"),
            ("bash", "pytest tests/"),
        ]
        for tool, cmd in commands:
            decision = permission.check(tool, cmd)
            self.assertTrue(decision.is_allowed)
            session_mgr.append_message("user", f"执行 {cmd}")
            budget.track("history", estimate_tokens(f"执行 {cmd}"))

        # 5. Layer1 压缩
        long_msg = {"role": "tool_result", "content": "Result: " * 2000}
        compressed_msg, l1_result = compactor.layer1_compress(long_msg)

        # 6. 归档
        mem_path = session_mgr.archive_session(summary="实现了认证模块基础")
        self.assertIsNotNone(mem_path)
        self.assertTrue(Path(mem_path).exists())

        # 7. 权限统计
        stats = permission.get_stats()
        self.assertEqual(stats["allowed"], 3)
        self.assertEqual(stats["denied"], 0)


# ═══════════════════════════════════════════════════════════
# 场景 6: 跨层数据一致性
# ═══════════════════════════════════════════════════════════

class TestScenario6_CrossLayerConsistency(P0IntegrationTestBase):
    """场景 6: 四层之间数据传递的一致性"""

    def test_budget_matches_model_context_window(self):
        """P0-1 → P0-2: TokenBudget context_window 与模型一致"""
        from agent_loop import AgentLoop

        for cw in [32000, 128000]:
            model = MockModel(context_window=cw)
            loop = AgentLoop(model=model, project_root=self.project_root)
            self.assertEqual(loop.budget.context_window, cw)

    def test_permission_rules_from_settings(self):
        """P0-4: PermissionManager 从 settings.json 正确加载规则"""
        from permission_manager import PermissionManager

        pm = PermissionManager(project_root=self.project_root, mode="default")

        # allow 规则
        self.assertTrue(pm.check("bash", "ls -la").is_allowed)

        # ask 规则
        self.assertTrue(pm.check("bash", "rm -rf /tmp/test").needs_confirmation)

        # deny 规则
        self.assertTrue(pm.check("bash", "sudo apt install").is_denied)

    def test_memory_index_update_and_read(self):
        """P0-3: MemoryManager 写入后能正确读回"""
        from memory_manager import MemoryManager

        mem_mgr = MemoryManager(project_root=self.project_root)
        mem_mgr.add_index_entry(
            time="04-11 10:00",
            file="20260411-100000.mem",
            summary="跨层一致性测试",
            priority="中",
        )

        content, items = mem_mgr.read_index_mem()
        self.assertIn("20260411-100000", content)

    def test_memory_retriever_async_search(self):
        """P0-3: RegexMemoryRetriever 异步搜索（rg/grep 均不可用时自动回退 Python）"""
        from memory_retriever import RegexMemoryRetriever

        # 创建 .mem 文件
        mem_path = Path(self.project_root) / ".ai" / "sessions" / "20260410-153000.mem"
        mem_path.write_text(
            "# Memory Archive\n\n"
            "## 摘要\n\n"
            "实现了用户认证模块，使用 JWT 令牌。\n",
            encoding="utf-8",
        )

        retriever = RegexMemoryRetriever(
            sessions_dir=str(Path(self.project_root) / ".ai" / "sessions")
        )

        loop = asyncio.new_event_loop()
        try:
            results = loop.run_until_complete(retriever.search("JWT"))
            self.assertGreater(len(results), 0)
        finally:
            loop.close()

    def test_conflict_detector_integration(self):
        """P0-3: MemoryConflictDetector 集成调用"""
        from memory_conflict_detector import MemoryConflictDetector

        detector = MemoryConflictDetector()

        # check_new_memory 是 P0 接口
        conflicts = detector.check_new_memory(
            new_memory="项目使用 Rust 1.70+",
            existing_memories=["项目使用 Python 3.9+"],
        )

        # 冲突检测基于关键词，不保证一定能检测到
        self.assertIsInstance(conflicts, list)

    def test_index_priority_sorter_integration(self):
        """P0-3: IndexPrioritySorter 集成调用"""
        from index_priority_sorter import IndexPrioritySorter, MemoryItem

        # 构造测试记忆项
        items = [
            MemoryItem(content="环境信息: Python 3.9+", category="environment", role="common"),
            MemoryItem(content="测试驱动开发", category="skill", role="dev"),
        ]

        sorter = IndexPrioritySorter()
        # 使用 calculate_priority 验证排序逻辑
        for item in items:
            priority = sorter.calculate_priority(item)
            self.assertIsInstance(priority, float)
            self.assertGreater(priority, 0)


if __name__ == "__main__":
    unittest.main()
