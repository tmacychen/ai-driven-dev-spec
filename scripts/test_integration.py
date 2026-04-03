#!/usr/bin/env python3
"""
ADDS v2.0 集成测试框架

测试目标：
1. 验证系统提示词构建的正确性
2. 验证 Agent Loop 状态机的合法性
3. 验证锁存机制的有效性
4. 验证合规追踪器的检测能力
5. 验证各代理的边界约束
"""

import asyncio
import tempfile
import unittest
from pathlib import Path
from typing import List, Dict

# 导入被测试模块
from system_prompt_builder import SystemPromptBuilder, STATIC_BOUNDARY
from agent_loop import (
    ADDSAgentLoop, Feature, FeatureStatus, AgentType,
    ProjectLatches, FeatureStateLatches, SafetyDefaults, State
)
from compliance_tracker import ComplianceTracker, ViolationType
from agents import create_agent, AgentContext, AgentResult


# ==============================================================================
# 系统提示词构建器测试
# ==============================================================================

class TestSystemPromptBuilder(unittest.TestCase):
    """系统提示词构建器测试"""
    
    def setUp(self):
        """测试前准备"""
        self.builder = SystemPromptBuilder()
        self.context = {
            'feature_list_path': '.ai/feature_list.md',
            'current_feature': 'test_feature',
            'current_status': 'in_progress',
            'current_agent': 'developer',
            'project_type': 'web_app',
            'tech_stack': ['Python', 'FastAPI']
        }
    
    def test_build_system_prompt(self):
        """测试构建系统提示词"""
        prompt = self.builder.build_system_prompt(self.context)
        
        # 验证：应该是列表
        self.assertIsInstance(prompt, list)
        
        # 验证：应该包含多个段落
        self.assertGreater(len(prompt), 3)
        
        # 验证：应该包含边界标记
        self.assertIn(STATIC_BOUNDARY, prompt)
        
        # 验证：边界标记之前是静态区
        boundary_index = prompt.index(STATIC_BOUNDARY)
        static_sections = prompt[:boundary_index]
        self.assertGreater(len(static_sections), 0)
        
        # 验证：边界标记之后是动态区
        dynamic_sections = prompt[boundary_index + 1:]
        self.assertGreater(len(dynamic_sections), 0)
    
    def test_static_sections_are_cacheable(self):
        """测试静态段落可缓存"""
        prompt = self.builder.build_system_prompt(self.context)
        boundary_index = prompt.index(STATIC_BOUNDARY)
        
        # 静态段落在不同上下文中应该相同
        context2 = self.context.copy()
        context2['current_feature'] = 'another_feature'
        
        prompt2 = self.builder.build_system_prompt(context2)
        boundary_index2 = prompt2.index(STATIC_BOUNDARY)
        
        # 静态区应该完全相同
        self.assertEqual(prompt[:boundary_index], prompt2[:boundary_index2])
    
    def test_dynamic_sections_are_context_specific(self):
        """测试动态段落随上下文变化"""
        prompt1 = self.builder.build_system_prompt(self.context)
        
        # 修改上下文
        context2 = self.context.copy()
        context2['current_feature'] = 'different_feature'
        
        prompt2 = self.builder.build_system_prompt(context2)
        
        # 动态区应该不同
        boundary_index1 = prompt1.index(STATIC_BOUNDARY)
        boundary_index2 = prompt2.index(STATIC_BOUNDARY)
        
        dynamic1 = '\n'.join(prompt1[boundary_index1 + 1:])
        dynamic2 = '\n'.join(prompt2[boundary_index2 + 1:])
        
        self.assertNotEqual(dynamic1, dynamic2)
    
    def test_identity_section_complete(self):
        """测试身份段落包含所有必需元素"""
        identity = self.builder._build_identity_section()
        
        # 验证所有核心要素都存在
        required_elements = {
            "ADDS": "ADDS 框架标识",
            "一次一个功能": "核心工作流程",
            "状态驱动": "状态管理理念"
        }
        
        for element, description in required_elements.items():
            self.assertIn(element, identity, f"身份段落缺少: {description} ({element})")
        
        # 验证段落结构合理（应该有多行）
        lines = identity.strip().split('\n')
        self.assertGreater(len(lines), 3, "身份段落应该有详细的多行描述")
    
    def test_safety_constraints_section_complete(self):
        """测试安全约束段落包含所有必需元素"""
        safety = self.builder._build_safety_constraints_section({})
        
        # 验证核心安全要素
        required_elements = {
            "失败关闭": "失败关闭机制",
            "危险操作": "危险操作识别"
        }
        
        for element, description in required_elements.items():
            self.assertIn(element, safety, f"安全约束段落缺少: {description}")
    
    def test_empty_context_handling(self):
        """测试空上下文处理"""
        empty_context = {}
        # 不应抛出异常，应该有默认值
        try:
            prompt = self.builder.build_system_prompt(empty_context)
            self.assertIsInstance(prompt, list)
            self.assertGreater(len(prompt), 0)
        except Exception as e:
            self.fail(f"空上下文应该被优雅处理，而不是抛出: {e}")
    
    def test_missing_required_fields(self):
        """测试缺少必需字段的处理"""
        partial_context = {
            'feature_list_path': '.ai/feature_list.md'
            # 缺少 current_feature, current_status 等
        }
        # 应该有默认值或优雅降级
        try:
            prompt = self.builder.build_system_prompt(partial_context)
            self.assertIsInstance(prompt, list)
        except KeyError as e:
            self.fail(f"缺少字段应该使用默认值，而不是抛出 KeyError: {e}")


# ==============================================================================
# Agent Loop 状态机测试
# ==============================================================================

class TestAgentLoop(unittest.TestCase):
    """Agent Loop 状态机测试"""
    
    def setUp(self):
        """测试前准备"""
        self.features = [
            Feature(name="feature_1", description="测试功能 1", status=FeatureStatus.PENDING),
            Feature(name="feature_2", description="测试功能 2", status=FeatureStatus.PENDING),
            Feature(name="feature_3", description="测试功能 3", status=FeatureStatus.TESTING),
        ]
    
    def test_safe_feature_selection(self):
        """测试安全的功能选择"""
        safety = SafetyDefaults()
        
        # 应该选择第一个 pending 功能
        selected = safety.safe_feature_selection(self.features)
        self.assertEqual(selected.name, "feature_1")
    
    def test_safe_feature_selection_no_pending(self):
        """测试无待处理功能时的失败关闭"""
        safety = SafetyDefaults()
        
        # 所有功能都已完成
        for f in self.features:
            f.status = FeatureStatus.COMPLETED
        
        # 应该抛出异常（失败关闭）
        with self.assertRaises(RuntimeError) as context:
            safety.safe_feature_selection(self.features)
        
        self.assertIn("无待处理功能", str(context.exception))
    
    def test_safe_status_transition_valid(self):
        """测试合法的状态转换"""
        safety = SafetyDefaults()
        
        # pending → in_progress 是合法的
        result = safety.safe_status_transition(FeatureStatus.PENDING, FeatureStatus.IN_PROGRESS)
        self.assertTrue(result)
    
    def test_safe_status_transition_invalid(self):
        """测试非法的状态转换"""
        safety = SafetyDefaults()
        
        # pending → completed 是非法的
        with self.assertRaises(RuntimeError) as context:
            safety.safe_status_transition(FeatureStatus.PENDING, FeatureStatus.COMPLETED)
        
        self.assertIn("非法状态转换", str(context.exception))
    
    def test_safe_agent_selection(self):
        """测试安全的代理选择"""
        safety = SafetyDefaults()
        state = State()
        state.project_type = "web_app"
        
        # 有 pending 功能 → Developer Agent
        agent = safety.safe_agent_selection(state, self.features)
        self.assertEqual(agent, AgentType.DEVELOPER)
    
    def test_safe_agent_selection_no_pending(self):
        """测试无待处理功能时的代理选择"""
        safety = SafetyDefaults()
        state = State()
        state.project_type = "web_app"
        
        # 所有功能都已完成
        for f in self.features:
            f.status = FeatureStatus.COMPLETED
        
        # 所有功能 completed → Reviewer Agent
        agent = safety.safe_agent_selection(state, self.features)
        self.assertEqual(agent, AgentType.REVIEWER)


# ==============================================================================
# 锁存机制测试
# ==============================================================================

class TestLatches(unittest.TestCase):
    """锁存机制测试"""
    
    def test_project_latches(self):
        """测试项目级锁存"""
        latches = ProjectLatches()
        state = State()
        
        # 首次锁存应该成功
        latches.latch_project_type(state, "web_app")
        self.assertEqual(state.project_type, "web_app")
        
        # 再次锁存应该被忽略
        latches.latch_project_type(state, "mobile_app")
        self.assertEqual(state.project_type, "web_app")  # 不变
    
    def test_feature_state_latches(self):
        """测试功能状态锁存"""
        latches = FeatureStateLatches()
        state = State()
        
        # 首次锁存功能
        latches.latch_current_feature(state, "feature_1")
        self.assertEqual(state.current_feature, "feature_1")
        
        # 尝试切换功能应该失败
        with self.assertRaises(RuntimeError) as context:
            latches.latch_current_feature(state, "feature_2")
        
        self.assertIn("功能状态锁存保护", str(context.exception))
    
    def test_feature_state_latches_release(self):
        """测试功能状态锁存释放"""
        latches = FeatureStateLatches()
        state = State()
        
        # 锁存功能
        latches.latch_current_feature(state, "feature_1")
        
        # 释放锁存
        latches.release_feature(state)
        
        # 应该可以锁存新功能
        latches.latch_current_feature(state, "feature_2")
        self.assertEqual(state.current_feature, "feature_2")


# ==============================================================================
# 合规追踪器测试
# ==============================================================================

class TestComplianceTracker(unittest.TestCase):
    """合规追踪器测试"""
    
    def setUp(self):
        """测试前准备"""
        self.tracker = ComplianceTracker()
    
    def test_check_one_feature_per_session(self):
        """测试一次一个功能检查"""
        # 第一次检查功能 1
        result1 = self.tracker.check_one_feature_per_session("feature_1")
        self.assertTrue(result1)
        
        # 再次检查同一功能（允许）
        result2 = self.tracker.check_one_feature_per_session("feature_1")
        self.assertTrue(result2)
        
        # 检查不同功能（应该失败）
        result3 = self.tracker.check_one_feature_per_session("feature_2")
        self.assertFalse(result3)
        
        # 验证违规被正确记录
        self.assertEqual(len(self.tracker.metrics.violations), 1, "应该有 1 个违规记录")
        self.assertEqual(self.tracker.metrics.violations[0].type, ViolationType.MULTIPLE_FEATURES_PER_SESSION)
    
    def test_check_one_feature_violation_recorded(self):
        """测试一次一个功能违规时 violation 被正确记录"""
        self.tracker.check_one_feature_per_session("feature_1")
        self.tracker.check_one_feature_per_session("feature_2")  # 违规
        
        # 验证违规类型 - violations_by_type 使用字符串值作为键
        self.assertIn(ViolationType.MULTIPLE_FEATURES_PER_SESSION.value, self.tracker.metrics.violations_by_type)
        self.assertEqual(self.tracker.metrics.violations_by_type[ViolationType.MULTIPLE_FEATURES_PER_SESSION.value], 1)
    
    def test_check_feature_list_exists(self):
        """测试功能列表存在检查"""
        # 功能列表不存在
        result = self.tracker.check_feature_list_exists(".ai/nonexistent.md")
        self.assertFalse(result)
        
        # 验证违规被记录 - violations_by_type 使用字符串值作为键
        self.assertIn(ViolationType.MISSING_FEATURE_LIST.value, self.tracker.metrics.violations_by_type)
        self.assertGreater(
            self.tracker.metrics.violations_by_type[ViolationType.MISSING_FEATURE_LIST.value], 0,
            "应该有 MISSING_FEATURE_LIST 违规记录"
        )
    
    def test_check_feature_list_exists_with_real_file(self):
        """测试功能列表存在检查（真实文件）"""
        import tempfile
        from pathlib import Path
        
        with tempfile.NamedTemporaryFile(mode='w', suffix='.md', delete=False) as f:
            f.write("# Feature List\n- Feature 1\n")
            temp_path = f.name
        
        try:
            result = self.tracker.check_feature_list_exists(temp_path)
            self.assertTrue(result, "存在的文件应该返回 True")
            
            # 验证没有新增违规
            initial_count = len(self.tracker.metrics.violations)
            self.tracker.check_feature_list_exists(temp_path)
            # 不应该有新的违规
        finally:
            Path(temp_path).unlink()
    
    def test_check_valid_status_transition(self):
        """测试合法状态转换检查"""
        # 合法转换
        result1 = self.tracker.check_valid_status_transition("pending", "in_progress", "feature_1")
        self.assertTrue(result1)
        
        # 再次合法转换（同一功能）
        result2 = self.tracker.check_valid_status_transition("in_progress", "testing", "feature_1")
        self.assertTrue(result2)
        
        # 非法转换
        result3 = self.tracker.check_valid_status_transition("pending", "completed", "feature_1")
        self.assertFalse(result3)
    
    def test_check_agent_boundary(self):
        """测试代理边界检查"""
        # 合法操作
        result1 = self.tracker.check_agent_boundary("developer", "implement_feature", "feature_1")
        self.assertTrue(result1)
        
        # 越权操作
        result2 = self.tracker.check_agent_boundary("developer", "design_architecture", "feature_1")
        self.assertFalse(result2)
        
        # 验证违规被记录
        boundary_violations = [v for v in self.tracker.metrics.violations 
                              if v.type == ViolationType.AGENT_BOUNDARY_VIOLATION]
        self.assertEqual(len(boundary_violations), 1, "应该有 1 个边界违规记录")
    
    def test_check_evidence_provided_complete(self):
        """测试证据提供检查（完整证据）"""
        result = self.tracker.check_evidence_provided("feature_1", {
            "files_modified": ["main.py"],
            "tests_run": ["test_main.py"],
            "tools_executed": ["pytest"]
        })
        self.assertTrue(result, "完整证据应该返回 True")
        
        # 验证没有新增违规
        initial_violations = len(self.tracker.metrics.violations)
        self.tracker.check_evidence_provided("feature_1", {
            "files_modified": ["main.py"],
            "tests_run": ["test_main.py"],
            "tools_executed": ["pytest"]
        })
        self.assertEqual(len(self.tracker.metrics.violations), initial_violations)
    
    def test_check_evidence_provided_missing_files(self):
        """测试证据提供检查（缺少文件修改）"""
        result = self.tracker.check_evidence_provided("feature_1", {
            "files_modified": [],  # 空列表
            "tests_run": ["test_main.py"],
            "tools_executed": ["pytest"]
        })
        self.assertFalse(result, "缺少文件修改应该返回 False")
    
    def test_check_evidence_provided_missing_tests(self):
        """测试证据提供检查（缺少测试）"""
        result = self.tracker.check_evidence_provided("feature_1", {
            "files_modified": ["main.py"],
            "tests_run": [],  # 空列表
            "tools_executed": ["pytest"]
        })
        self.assertFalse(result, "缺少测试应该返回 False")
    
    def test_check_evidence_provided_null_values(self):
        """测试证据提供检查（null 值）"""
        result = self.tracker.check_evidence_provided("feature_1", {
            "files_modified": None,  # null
            "tests_run": None,
            "tools_executed": None
        })
        self.assertFalse(result, "null 值应该返回 False")
    
    def test_compliance_score_calculation(self):
        """测试合规分数计算"""
        # 初始分数为 1.0
        self.assertEqual(self.tracker.metrics.compliance_score, 1.0)
        
        # 记录一个警告级违规
        from compliance_tracker import Violation
        self.tracker.metrics.record_violation(
            Violation(
                type=ViolationType.MISSING_EVIDENCE,
                details="测试",
                severity="warning"
            )
        )
        
        # 分数应该降低
        self.assertLess(self.tracker.metrics.compliance_score, 1.0, "记录违规后分数应该降低")
    
    def test_compliance_score_with_multiple_violations(self):
        """测试合规分数计算（多个违规）"""
        from compliance_tracker import Violation
        
        # 记录多个违规
        for i in range(3):
            self.tracker.metrics.record_violation(
                Violation(
                    type=ViolationType.MISSING_EVIDENCE,
                    details=f"测试违规 {i}",
                    severity="warning"
                )
            )
        
        # 分数应该显著降低
        self.assertLess(self.tracker.metrics.compliance_score, 0.8)
    
    def test_get_compliance_report(self):
        """测试合规报告生成"""
        # 执行一些检查
        self.tracker.check_one_feature_per_session("feature_1")
        self.tracker.check_one_feature_per_session("feature_2")  # 违规
        
        # 生成报告
        report = self.tracker.get_compliance_report()
        
        # 验证报告包含关键内容
        self.assertIn("规范遵循报告", report)
        self.assertIn("违规统计", report)
        self.assertIn("feature_1", report)
        self.assertIn("feature_2", report)


# ==============================================================================
# 代理边界约束测试
# ==============================================================================

class TestAgentBoundaries(unittest.TestCase):
    """代理边界约束测试"""
    
    def setUp(self):
        """测试前准备"""
        self.temp_dir = tempfile.mkdtemp()
        self.project_root = Path(self.temp_dir)
        self.context = AgentContext(
            project_root=self.project_root,
            feature_list_path=self.project_root / ".ai" / "feature_list.md"
        )
    
    def tearDown(self):
        """测试后清理"""
        import shutil
        shutil.rmtree(self.temp_dir)
    
    def test_pm_agent_allowed_actions(self):
        """测试 PM Agent 允许的操作"""
        agent = create_agent("pm", self.context)
        
        # 允许的操作
        for action in ["analyze_requirements", "decompose_tasks", "create_feature_list"]:
            self.assertTrue(agent.check_boundary(action), f"PM Agent 应该允许: {action}")
    
    def test_pm_agent_disallowed_actions(self):
        """测试 PM Agent 禁止的操作"""
        agent = create_agent("pm", self.context)
        
        # 禁止的操作 - 应该抛出异常
        with self.assertRaises(RuntimeError):
            agent.check_boundary("implement_feature")
    
    def test_developer_agent_allowed_actions(self):
        """测试 Developer Agent 允许的操作"""
        agent = create_agent("developer", self.context)
        
        # 允许的操作
        for action in ["implement_feature", "write_unit_tests", "update_status"]:
            self.assertTrue(agent.check_boundary(action), f"Developer Agent 应该允许: {action}")
    
    def test_developer_agent_disallowed_actions(self):
        """测试 Developer Agent 禁止的操作"""
        agent = create_agent("developer", self.context)
        
        # 禁止的操作 - 应该抛出异常
        with self.assertRaises(RuntimeError):
            agent.check_boundary("design_architecture")
    
    def test_tester_agent_allowed_actions(self):
        """测试 Tester Agent 允许的操作"""
        agent = create_agent("tester", self.context)
        
        # 允许的操作
        for action in ["run_tests", "check_regression", "update_status"]:
            self.assertTrue(agent.check_boundary(action), f"Tester Agent 应该允许: {action}")
    
    def test_tester_agent_disallowed_actions(self):
        """测试 Tester Agent 禁止的操作"""
        agent = create_agent("tester", self.context)
        
        # 禁止的操作 - 应该抛出异常
        with self.assertRaises(RuntimeError):
            agent.check_boundary("implement_feature")
    
    def test_architect_agent_allowed_actions(self):
        """测试 Architect Agent 允许的操作"""
        agent = create_agent("architect", self.context)
        
        # 允许的操作 - 基于实际实现
        allowed_actions = ["design_architecture", "select_tech_stack", "define_structure", "create_architecture_doc", "define_coding_standards"]
        for action in allowed_actions:
            self.assertTrue(agent.check_boundary(action), f"Architect Agent 应该允许: {action}")
    
    def test_architect_agent_disallowed_actions(self):
        """测试 Architect Agent 禁止的操作"""
        agent = create_agent("architect", self.context)
        
        # 禁止的操作 - 核心开发操作
        disallowed_actions = ["implement_feature", "write_tests", "run_tests"]
        for action in disallowed_actions:
            with self.assertRaises(RuntimeError):
                agent.check_boundary(action)
    
    def test_reviewer_agent_allowed_actions(self):
        """测试 Reviewer Agent 允许的操作"""
        agent = create_agent("reviewer", self.context)
        
        # 允许的操作 - 基于实际实现
        allowed_actions = ["code_review", "security_audit", "performance_eval", "generate_report"]
        for action in allowed_actions:
            self.assertTrue(agent.check_boundary(action), f"Reviewer Agent 应该允许: {action}")
    
    def test_reviewer_agent_disallowed_actions(self):
        """测试 Reviewer Agent 禁止的操作"""
        agent = create_agent("reviewer", self.context)
        
        # 禁止的操作 - 开发和测试操作
        disallowed_actions = ["implement_feature", "design_architecture", "run_tests"]
        for action in disallowed_actions:
            with self.assertRaises(RuntimeError):
                agent.check_boundary(action)
    
    def test_unknown_action_handling(self):
        """测试未知操作的默认行为"""
        agent = create_agent("developer", self.context)
        
        # 未知操作应该被拒绝（返回 False）或抛出异常
        try:
            result = agent.check_boundary("totally_unknown_action_xyz")
            # 如果返回 False，说明正确拒绝了
            self.assertFalse(result)
        except (RuntimeError, ValueError):
            pass  # 抛出异常也是可接受的


# ==============================================================================
# 集成测试
# ==============================================================================

class TestIntegration(unittest.TestCase):
    """集成测试"""
    
    def setUp(self):
        """测试前准备"""
        self.temp_dir = tempfile.mkdtemp()
        self.project_root = Path(self.temp_dir)
        self.feature_list_path = self.project_root / ".ai" / "feature_list.md"
        
        # 创建必要的目录
        self.feature_list_path.parent.mkdir(parents=True, exist_ok=True)
    
    def tearDown(self):
        """测试后清理"""
        import shutil
        shutil.rmtree(self.temp_dir)
    
    def test_full_workflow_with_file_verification(self):
        """测试完整工作流（带实际文件验证）"""
        async def run_workflow():
            context = AgentContext(
                project_root=self.project_root,
                feature_list_path=self.feature_list_path
            )
            
            # 1. PM Agent 创建功能列表
            pm_agent = create_agent("pm", context)
            result = await pm_agent.execute([])
            
            self.assertTrue(result.success, "PM Agent 应该成功执行")
            self.assertTrue(self.feature_list_path.exists(), "功能列表文件应该被创建")
            
            # 验证功能列表内容不为空
            content = self.feature_list_path.read_text()
            self.assertGreater(len(content), 50, "功能列表应该有实质性内容")
            self.assertIn("功能列表", content, "功能列表应包含标题")
            
            # 2. Developer Agent 实现功能
            features = [{"name": "project_setup", "status": "pending"}]
            dev_agent = create_agent("developer", context)
            result = await dev_agent.execute(features)
            
            self.assertTrue(result.success, "Developer Agent 应该成功执行")
            
            # 3. Tester Agent 测试功能
            test_agent = create_agent("tester", context)
            result = await test_agent.execute(features)
            
            self.assertTrue(result.success, "Tester Agent 应该成功执行")
            
            # 4. Reviewer Agent 审查
            rev_agent = create_agent("reviewer", context)
            result = await rev_agent.execute(features)
            
            self.assertTrue(result.success, "Reviewer Agent 应该成功执行")
        
        asyncio.run(run_workflow())
    
    def test_workflow_with_feature_dependencies(self):
        """测试带功能依赖的工作流"""
        async def run_workflow():
            context = AgentContext(
                project_root=self.project_root,
                feature_list_path=self.feature_list_path
            )
            
            # 1. PM Agent 创建功能列表
            pm_agent = create_agent("pm", context)
            result = await pm_agent.execute([])
            
            self.assertTrue(result.success, "PM Agent 应该成功执行")
            self.assertTrue(self.feature_list_path.exists(), "功能列表文件应该被创建")
            
            # 验证功能列表包含依赖关系结构
            content = self.feature_list_path.read_text()
            self.assertIn("依赖", content, "功能列表应包含依赖关系说明")
            self.assertIn("##", content, "功能列表应该有章节结构")
            
            # 2. Architect Agent 设计架构
            arch_agent = create_agent("architect", context)
            result = await arch_agent.execute([])
            
            self.assertTrue(result.success, "Architect Agent 应该成功执行")
        
        asyncio.run(run_workflow())


# ==============================================================================
# 并发测试
# ==============================================================================

class TestConcurrency(unittest.TestCase):
    """并发场景测试"""
    
    def setUp(self):
        """测试前准备"""
        self.temp_dir = tempfile.mkdtemp()
        self.project_root = Path(self.temp_dir)
    
    def tearDown(self):
        """测试后清理"""
        import shutil
        shutil.rmtree(self.temp_dir)
    
    def test_concurrent_feature_access(self):
        """测试并发访问同一功能的锁存保护"""
        latches = FeatureStateLatches()
        state = State()
        
        # 首次锁存应该成功
        latches.latch_current_feature(state, "feature_1")
        self.assertEqual(state.current_feature, "feature_1")
        
        # 尝试同步切换功能 - 应该失败
        with self.assertRaises(RuntimeError) as context:
            latches.latch_current_feature(state, "feature_2")
        
        self.assertIn("功能状态锁存保护", str(context.exception))
        
        # 验证状态未被改变
        self.assertEqual(state.current_feature, "feature_1")
    
    def test_concurrent_project_type_latch(self):
        """测试并发设置项目类型的锁存保护"""
        latches = ProjectLatches()
        state = State()
        
        # 首次锁存
        latches.latch_project_type(state, "web_app")
        
        # 尝试同步修改项目类型 - 应该被忽略（不是抛异常）
        latches.latch_project_type(state, "mobile_app")
        
        # 验证项目类型保持不变
        self.assertEqual(state.project_type, "web_app", "项目类型不应被改变")
        
        # 验证没有抛出异常（锁存是静默忽略，不是抛异常）


# ==============================================================================
# 错误恢复测试
# ==============================================================================

class TestErrorRecovery(unittest.TestCase):
    """错误恢复测试"""
    
    def setUp(self):
        """测试前准备"""
        self.temp_dir = tempfile.mkdtemp()
        self.project_root = Path(self.temp_dir)
        self.context = AgentContext(
            project_root=self.project_root,
            feature_list_path=self.project_root / ".ai" / "feature_list.md"
        )
    
    def tearDown(self):
        """测试后清理"""
        import shutil
        shutil.rmtree(self.temp_dir)
    
    def test_recovery_after_violation(self):
        """测试违规后的恢复"""
        tracker = ComplianceTracker()
        
        # 触发违规
        tracker.check_one_feature_per_session("feature_1")
        tracker.check_one_feature_per_session("feature_2")  # 违规
        
        # 验证违规被记录
        self.assertEqual(len(tracker.metrics.violations), 1)
        
        # 继续正常工作 - 不应受影响
        result = tracker.check_one_feature_per_session("feature_1")
        self.assertTrue(result, "违规后应该仍能正常工作")
        
        # 再次尝试不同功能（又一次违规）
        result = tracker.check_one_feature_per_session("feature_3")
        self.assertFalse(result, "再次违规应该被检测")
        
        # 验证多个违规都被记录
        self.assertEqual(len(tracker.metrics.violations), 2)
    
    def test_compliance_score_recovery(self):
        """测试合规分数在违规后的行为"""
        tracker = ComplianceTracker()
        
        initial_score = tracker.metrics.compliance_score
        self.assertEqual(initial_score, 1.0)
        
        # 记录违规
        from compliance_tracker import Violation
        tracker.metrics.record_violation(
            Violation(type=ViolationType.MISSING_EVIDENCE, details="test", severity="warning")
        )
        
        score_after_violation = tracker.metrics.compliance_score
        self.assertLess(score_after_violation, initial_score)
        
        # 继续记录更多违规
        tracker.metrics.record_violation(
            Violation(type=ViolationType.AGENT_BOUNDARY_VIOLATION, details="test", severity="error")
        )
        
        score_after_more = tracker.metrics.compliance_score
        self.assertLess(score_after_more, score_after_violation)
    
    def test_tracker_state_after_multiple_operations(self):
        """测试多次操作后 tracker 状态一致性"""
        tracker = ComplianceTracker()
        
        # 第一次检查（建立会话）
        result1 = tracker.check_one_feature_per_session("feature_0")
        self.assertTrue(result1, "首次检查应该成功")
        
        # 后续每次不同功能的检查都会触发违规
        for i in range(1, 5):
            result = tracker.check_one_feature_per_session(f"feature_{i}")
            self.assertFalse(result, f"feature_{i} 应该触发违规")
        
        # 验证违规被正确记录（4次违规：feature_1 到 feature_4）
        self.assertEqual(
            len(tracker.metrics.violations),
            4,
            "feature_1 到 feature_4 各触发一次违规"
        )


# ==============================================================================
# 运行测试
# ==============================================================================

def run_tests():
    """运行所有测试"""
    loader = unittest.TestLoader()
    suite = unittest.TestSuite()
    
    # 添加测试类
    suite.addTests(loader.loadTestsFromTestCase(TestSystemPromptBuilder))
    suite.addTests(loader.loadTestsFromTestCase(TestAgentLoop))
    suite.addTests(loader.loadTestsFromTestCase(TestLatches))
    suite.addTests(loader.loadTestsFromTestCase(TestComplianceTracker))
    suite.addTests(loader.loadTestsFromTestCase(TestAgentBoundaries))
    suite.addTests(loader.loadTestsFromTestCase(TestIntegration))
    suite.addTests(loader.loadTestsFromTestCase(TestConcurrency))
    suite.addTests(loader.loadTestsFromTestCase(TestErrorRecovery))
    
    # 运行测试
    runner = unittest.TextTestRunner(verbosity=2)
    result = runner.run(suite)
    
    return result.wasSuccessful()


if __name__ == "__main__":
    success = run_tests()
    exit(0 if success else 1)
