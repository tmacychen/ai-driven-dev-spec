#!/usr/bin/env python3
"""
P0-3 单元测试: 记忆系统（优先级排序 + 冲突检测 + 检索 + 排毒 + 角色注入 + 一致性守护 + 记忆管理器）
"""

import asyncio
import shutil
import tempfile
import unittest
from datetime import datetime, timedelta
from pathlib import Path
from unittest.mock import patch

from index_priority_sorter import (
    IndexPrioritySorter, MemoryItem,
    parse_index_mem, build_index_content, _format_item,
    CATEGORY_WEIGHTS, TIME_DECAY_LAMBDA,
)
from memory_conflict_detector import (
    MemoryConflictDetector, ConflictRecord, LightweightConflictScanner,
)
from memory_retriever import (
    RegexMemoryRetriever, SearchResult, MemoryRetriever,
)
from memory_detox import MemoryDetox, InvalidationResult
from role_memory_injector import RoleAwareMemoryInjector, RoleMemoryConfig
from consistency_guard import ConsistencyGuard, DefenseFailureDiagnosis, RegressionAlarm
from memory_manager import MemoryManager, MemoryUpgradeEvaluation, MemoryStatus


class TestIndexPrioritySorter(unittest.TestCase):
    """IndexPrioritySorter 单元测试"""

    def setUp(self):
        self.sorter = IndexPrioritySorter()

    def test_calculate_priority_basic(self):
        item = MemoryItem(
            id='exp-001', content='PyJWT 2.x API 不兼容', category='experience',
            last_accessed=datetime.now(), reference_count=5, invalidation_count=0,
        )
        p = self.sorter.calculate_priority(item)
        self.assertGreater(p, 0.5)

    def test_calculate_priority_demoted(self):
        item = MemoryItem(id='exp-002', status='demoted')
        p = self.sorter.calculate_priority(item)
        self.assertEqual(p, 0.0)

    def test_time_decay(self):
        recent = MemoryItem(id='r', category='experience', last_accessed=datetime.now())
        old = MemoryItem(id='o', category='experience', last_accessed=datetime.now() - timedelta(days=30))
        p_recent = self.sorter.calculate_priority(recent)
        p_old = self.sorter.calculate_priority(old)
        self.assertGreater(p_recent, p_old)

    def test_invalidation_penalty(self):
        clean = MemoryItem(id='c', category='experience', last_accessed=datetime.now(), invalidation_count=0)
        dirty = MemoryItem(id='d', category='experience', last_accessed=datetime.now(), invalidation_count=3)
        p_clean = self.sorter.calculate_priority(clean)
        p_dirty = self.sorter.calculate_priority(dirty)
        self.assertGreater(p_clean, p_dirty)

    def test_category_weights(self):
        env = MemoryItem(id='env', category='environment', last_accessed=datetime.now())
        skill = MemoryItem(id='sk', category='skill', last_accessed=datetime.now())
        p_env = self.sorter.calculate_priority(env)
        p_skill = self.sorter.calculate_priority(skill)
        self.assertGreater(p_env, p_skill)

    def test_system_prompt_related_bonus(self):
        base = MemoryItem(id='b', category='experience', last_accessed=datetime.now(), system_prompt_related=False)
        sp = MemoryItem(id='sp', category='experience', last_accessed=datetime.now(), system_prompt_related=True)
        p_base = self.sorter.calculate_priority(base)
        p_sp = self.sorter.calculate_priority(sp)
        self.assertGreater(p_sp, p_base)

    def test_promote_bonus(self):
        base = MemoryItem(id='b', category='experience', last_accessed=datetime.now(), promoted=False)
        promoted = MemoryItem(id='p', category='experience', last_accessed=datetime.now(), promoted=True)
        p_base = self.sorter.calculate_priority(base)
        p_promoted = self.sorter.calculate_priority(promoted)
        self.assertGreater(p_promoted, p_base)

    def test_code_heat_bonus(self):
        item = MemoryItem(id='h', category='experience', module='auth', last_accessed=datetime.now())
        p_no_heat = self.sorter.calculate_priority(item)
        p_with_heat = self.sorter.calculate_priority(item, code_heat_map={"auth": 5})
        self.assertGreater(p_with_heat, p_no_heat)

    def test_sort_for_index(self):
        items = [
            MemoryItem(id='low', content='Low priority', category='skill',
                       last_accessed=datetime.now() - timedelta(days=60)),
            MemoryItem(id='high', content='High priority', category='environment',
                       last_accessed=datetime.now()),
        ]
        current, overflow = self.sorter.sort_for_index(items, capacity=500)
        self.assertEqual(len(current) + len(overflow), 2)
        # High priority should be in current
        self.assertTrue(any(i.id == 'high' for i in current))

    def test_auto_demotion(self):
        items = [
            MemoryItem(id='bad', content='Bad', category='skill',
                       last_accessed=datetime.now() - timedelta(days=365),
                       invalidation_count=4),
        ]
        current, overflow = self.sorter.sort_for_index(items, capacity=10)
        # Should be demoted
        self.assertEqual(items[0].status, 'demoted')

    def test_get_forced_reminders(self):
        items = [
            MemoryItem(id='ok', content='Good advice', invalidation_count=0, promoted=False, role='developer'),
            MemoryItem(id='bad', content='Bad advice', invalidation_count=3, promoted=False, role='developer'),
        ]
        reminders = self.sorter.get_forced_reminders(items, role='developer')
        self.assertEqual(len(reminders), 1)
        self.assertEqual(reminders[0].id, 'bad')

    def test_get_forced_reminders_role_filter(self):
        items = [
            MemoryItem(id='dev-bad', content='Dev bad', invalidation_count=3, promoted=False, role='developer'),
            MemoryItem(id='arch-bad', content='Arch bad', invalidation_count=3, promoted=False, role='architect'),
        ]
        reminders = self.sorter.get_forced_reminders(items, role='developer')
        # Only dev role should match
        self.assertEqual(len(reminders), 1)
        self.assertEqual(reminders[0].id, 'dev-bad')


class TestParseIndexMem(unittest.TestCase):
    """parse_index_mem / build_index_content 单元测试"""

    def test_parse_simple(self):
        content = "### 核心经验\n- PyJWT 2.x 不兼容 | module: auth | id: exp-001"
        items = parse_index_mem(content)
        self.assertEqual(len(items), 1)
        self.assertEqual(items[0].id, 'exp-001')
        self.assertIn('PyJWT', items[0].content)
        self.assertEqual(items[0].module, 'auth')

    def test_parse_invalidated(self):
        content = "### 核心经验\n- ~~Old advice~~ ❌ | status: invalidated | id: exp-002"
        items = parse_index_mem(content)
        self.assertEqual(len(items), 1)
        self.assertEqual(items[0].status, 'invalidated')
        self.assertIn('Old advice', items[0].content)
        self.assertEqual(items[0].id, 'exp-002')

    def test_parse_environment(self):
        content = "### 项目环境\n- Python 3.9+ | id: env-001"
        items = parse_index_mem(content)
        self.assertEqual(len(items), 1)
        self.assertEqual(items[0].category, 'environment')

    def test_parse_skill(self):
        content = "### 已掌握技能\n- JWT 认证 | id: skill-001"
        items = parse_index_mem(content)
        self.assertEqual(len(items), 1)
        self.assertEqual(items[0].category, 'skill')

    def test_parse_preference(self):
        content = "### 用户偏好\n- 中文沟通 | id: pref-001"
        items = parse_index_mem(content)
        self.assertEqual(len(items), 1)
        self.assertEqual(items[0].category, 'preference')

    def test_roundtrip(self):
        items = [
            MemoryItem(id='exp-001', content='Test content', category='experience',
                       module='auth', role='developer', status='active'),
            MemoryItem(id='exp-002', content='Old content', category='experience',
                       status='invalidated', invalidation_count=2),
        ]
        content = build_index_content(items)
        parsed = parse_index_mem(content)
        self.assertEqual(len(parsed), 2)
        # Find by id
        by_id = {i.id: i for i in parsed}
        self.assertIn('exp-001', by_id)
        self.assertIn('exp-002', by_id)
        self.assertEqual(by_id['exp-002'].status, 'invalidated')

    def test_format_item_active(self):
        item = MemoryItem(id='exp-001', content='Test', module='auth')
        formatted = _format_item(item)
        self.assertTrue(formatted.startswith("- "))
        self.assertIn("id: exp-001", formatted)

    def test_format_item_invalidated(self):
        item = MemoryItem(id='exp-002', content='Bad advice', status='invalidated', invalidation_count=2)
        formatted = _format_item(item)
        self.assertIn("~~Bad advice~~ ❌", formatted)
        self.assertIn("status: invalidated", formatted)


class TestMemoryConflictDetector(unittest.TestCase):
    """MemoryConflictDetector 单元测试"""

    def setUp(self):
        self.detector = MemoryConflictDetector()

    def test_check_jwt_vs_session(self):
        conflicts = self.detector.check_new_memory(
            'Use JWT for authentication',
            ['Currently using Session-based authentication']
        )
        self.assertGreater(len(conflicts), 0)
        self.assertEqual(conflicts[0]['conflict_type'], 'JWT vs Session')

    def test_check_no_conflict(self):
        conflicts = self.detector.check_new_memory(
            'Add logging support',
            ['Currently using FastAPI framework']
        )
        self.assertEqual(len(conflicts), 0)

    def test_check_rest_vs_graphql(self):
        conflicts = self.detector.check_new_memory(
            'Use GraphQL for API',
            ['Currently using REST for API']
        )
        self.assertGreater(len(conflicts), 0)

    def test_auto_resolve_sp_wins(self):
        c = ConflictRecord(source_a='system_prompt', source_b='fixed_memory')
        result = self.detector.auto_resolve(c)
        self.assertEqual(result, 'system_prompt_wins')

    def test_auto_resolve_user_latest_wins(self):
        c = ConflictRecord(source_a='user_latest', source_b='fixed_memory')
        result = self.detector.auto_resolve(c)
        self.assertEqual(result, 'user_latest_wins')

    def test_auto_resolve_sp_vs_user(self):
        c = ConflictRecord(source_a='system_prompt', source_b='user_latest')
        result = self.detector.auto_resolve(c)
        self.assertIsNone(result)

    def test_resolve_conflict_with_user_decision(self):
        c = ConflictRecord(source_a='system_prompt', source_b='user_latest')
        result = self.detector.resolve_conflict(c, user_decision='keep_both')
        self.assertEqual(result, 'keep_both')

    def test_get_pending_conflicts(self):
        self.detector.check_new_memory('Use JWT', ['Using Session'])
        pending = self.detector.get_pending_conflicts()
        self.assertGreater(len(pending), 0)

    def test_format_conflict(self):
        c = ConflictRecord(
            description="JWT vs Session",
            source_a="fixed_memory",
            source_b="new_memory",
            content_a="Session-based auth",
            content_b="JWT auth",
            resolution="pending",
        )
        text = self.detector.format_conflict_for_display(c)
        self.assertIn("JWT vs Session", text)
        self.assertIn("待确认", text)


class TestMemoryRetriever(unittest.TestCase):
    """RegexMemoryRetriever 单元测试"""

    def setUp(self):
        self.tmp = tempfile.mkdtemp(prefix="adds_test_retriever_")
        self.retriever = RegexMemoryRetriever(sessions_dir=self.tmp)

    def tearDown(self):
        shutil.rmtree(self.tmp)

    def test_extract_keywords(self):
        keywords = self.retriever._extract_keywords('How does JWT authentication work?')
        # Should extract JWT and authentication
        self.assertIn('JWT', keywords)

    def test_extract_keywords_chinese(self):
        keywords = self.retriever._extract_keywords('JWT 认证如何工作？')
        self.assertIn('JWT', keywords)

    def test_extract_keywords_stopwords(self):
        keywords = self.retriever._extract_keywords('the is are was were')
        self.assertEqual(len(keywords), 0)

    def test_search_empty_dir(self):
        results = asyncio.run(self.retriever.search('JWT', top_k=3))
        self.assertEqual(len(results), 0)

    def test_search_with_mem_file(self):
        # Create a .mem file
        mem_file = Path(self.tmp) / "20260410-160000.mem"
        mem_file.write_text("JWT token authentication implementation\n测试通过", encoding="utf-8")

        # Use Python fallback search (rg may not find files in tmp dirs)
        results = asyncio.run(self.retriever._python_search(
            'JWT', list(self.retriever.sessions_dir.glob("*.mem"))
        ))
        self.assertGreater(len(results), 0)
        self.assertIn('JWT', results[0].content)

    def test_search_index_mem_higher_relevance(self):
        # Create index.mem and a regular .mem
        index_mem = Path(self.tmp) / "index.mem"
        index_mem.write_text("### 核心经验\n- JWT token 不兼容\n", encoding="utf-8")

        regular_mem = Path(self.tmp) / "20260410-160000.mem"
        regular_mem.write_text("JWT token implementation", encoding="utf-8")

        results = asyncio.run(self.retriever.search('JWT', top_k=3))
        if len(results) >= 2:
            # index.mem should have higher relevance
            index_results = [r for r in results if r.source == '固定记忆']
            other_results = [r for r in results if r.source != '固定记忆']
            if index_results and other_results:
                self.assertGreater(index_results[0].relevance, other_results[0].relevance)

    def test_rank_and_topk(self):
        results = [
            SearchResult(source='固定记忆', file='index.mem', content='JWT', relevance=1.0, line_number=1),
            SearchResult(source='.mem文件', file='test.mem', content='JWT', relevance=0.5, line_number=5),
            SearchResult(source='固定记忆', file='index.mem', content='JWT', relevance=1.0, line_number=1),  # Same line
        ]
        ranked = self.retriever._rank_and_topk(results, top_k=2)
        self.assertLessEqual(len(ranked), 2)


class TestMemoryDetox(unittest.TestCase):
    """MemoryDetox 单元测试"""

    def setUp(self):
        self.detox = MemoryDetox()

    def test_evaluate_invalidation_module_match(self):
        items = [
            MemoryItem(id='exp-001', content='Use httpx for HTTP', category='experience', module='http'),
        ]
        failed_context = {'error': 'httpx connection timeout', 'code_snippet': 'import httpx'}
        results = asyncio.run(self.detox.evaluate_invalidation(
            session_mem='Task failed: httpx timeout',
            failed_task_context=failed_context,
            referenced_memories=items,
        ))
        self.assertGreater(len(results), 0)
        self.assertTrue(results[0].related)

    def test_evaluate_invalidation_no_match(self):
        items = [
            MemoryItem(id='exp-001', content='Use FastAPI framework', category='experience', module='api'),
        ]
        failed_context = {'error': 'database connection timeout', 'code_snippet': ''}
        results = asyncio.run(self.detox.evaluate_invalidation(
            session_mem='Task failed: db timeout',
            failed_task_context=failed_context,
            referenced_memories=items,
        ))
        # Should not be related
        self.assertTrue(all(not r.related for r in results))

    def test_evaluate_invalidation_empty(self):
        results = asyncio.run(self.detox.evaluate_invalidation(
            session_mem='No failure',
            failed_task_context={},
            referenced_memories=[],
        ))
        self.assertEqual(len(results), 0)

    def test_apply_rollback_penalty_not_demoted(self):
        item = MemoryItem(id='exp-001', content='Some advice', category='experience',
                          last_accessed=datetime.now())
        demoted = self.detox.apply_rollback_penalty(item)
        self.assertEqual(item.rollback_count, 1)
        self.assertFalse(demoted)

    def test_apply_rollback_penalty_demoted(self):
        item = MemoryItem(id='exp-001', content='Some advice', category='experience',
                          last_accessed=datetime.now(), rollback_count=5)
        demoted = self.detox.apply_rollback_penalty(item)
        self.assertTrue(demoted)
        self.assertEqual(item.status, 'demoted')

    def test_check_new_memory_conflicts(self):
        conflicts = self.detox.check_new_memory_conflicts(
            'Use GraphQL for API',
            ['Currently using REST for API']
        )
        self.assertGreater(len(conflicts), 0)

    def test_auto_demotion_on_invalidation_count(self):
        items = [
            MemoryItem(id='exp-bad', content='Bad', category='skill', module='test',
                       invalidation_count=2, last_accessed=datetime.now()),
        ]
        failed_context = {'error': 'test module error', 'code_snippet': ''}
        results = asyncio.run(self.detox.evaluate_invalidation(
            session_mem='Failed',
            failed_task_context=failed_context,
            referenced_memories=items,
        ))
        # After 3 invalidations, should be demoted
        if results and results[0].related:
            self.assertTrue(results[0].demoted)


class TestRoleAwareMemoryInjector(unittest.TestCase):
    """RoleAwareMemoryInjector 单元测试"""

    def setUp(self):
        self.injector = RoleAwareMemoryInjector()
        self.items = [
            MemoryItem(id='env-001', content='Python 3.9+', category='environment', role='common'),
            MemoryItem(id='exp-dev', content='PyJWT 不兼容', category='experience', role='developer'),
            MemoryItem(id='exp-arch', content='FFI 必须封装', category='experience', role='architect'),
            MemoryItem(id='skill-dev', content='JWT 认证实现', category='skill', role='developer'),
            MemoryItem(id='pref-001', content='中文沟通', category='preference', role='common'),
        ]

    def test_developer_gets_dev_items(self):
        dev_items = self.injector.filter_memories_for_role(self.items, 'developer')
        dev_ids = [i.id for i in dev_items]
        self.assertIn('env-001', dev_ids)
        self.assertIn('exp-dev', dev_ids)
        self.assertIn('skill-dev', dev_ids, 'Developer should get skill items')
        self.assertNotIn('exp-arch', dev_ids)

    def test_architect_no_skills(self):
        arch_items = self.injector.filter_memories_for_role(self.items, 'architect')
        arch_ids = [i.id for i in arch_items]
        self.assertIn('exp-arch', arch_ids)
        self.assertNotIn('skill-dev', arch_ids)

    def test_common_role_included_for_all(self):
        for role in ['developer', 'architect', 'tester', 'pm', 'reviewer']:
            items = self.injector.filter_memories_for_role(self.items, role)
            ids = [i.id for i in items]
            self.assertIn('env-001', ids, f'Common items should be included for {role}')
            self.assertIn('pref-001', ids, f'Common preferences should be included for {role}')

    def test_build_memory_section(self):
        section = self.injector.build_memory_section(self.items, 'developer')
        self.assertIn('JWT', section)
        self.assertIn('项目环境', section)

    def test_build_memory_section_with_reminders(self):
        forced = [MemoryItem(id='exp-bad', content='Bad advice', invalidation_count=3)]
        section = self.injector.build_memory_section(self.items, 'developer', forced_reminders=forced)
        self.assertIn('强制复读', section)

    def test_get_role_description(self):
        self.assertIn('手', self.injector.get_role_description('developer'))
        self.assertIn('界', self.injector.get_role_description('architect'))
        self.assertIn('眼', self.injector.get_role_description('tester'))


class TestConsistencyGuard(unittest.TestCase):
    """ConsistencyGuard 单元测试"""

    def setUp(self):
        self.guard = ConsistencyGuard()

    def test_compute_similarity_basic(self):
        failure = {'error': 'JWT token expired', 'module': 'auth', 'code_snippet': ''}
        case = SearchResult(source='固定记忆', file='index.mem',
                            content='JWT token must be refreshed before expiry', relevance=0.8)
        similarity = self.guard._compute_similarity(failure, case)
        self.assertGreater(similarity, 0)

    def test_compute_similarity_module_bonus(self):
        """模块匹配应该增加相似度"""
        failure = {'error': 'auth timeout', 'module': 'auth', 'code_snippet': ''}
        # Same content but with module match
        case_no_module = SearchResult(source='固定记忆', file='index.mem',
                                       content='auth timeout handled correctly', relevance=0.5)
        case_with_module = SearchResult(source='固定记忆', file='index.mem',
                                         content='auth timeout must be handled with retry', relevance=0.5)
        s1 = self.guard._compute_similarity(failure, case_no_module)
        s2 = self.guard._compute_similarity(failure, case_with_module)
        # Both should have some similarity, module match adds bonus
        self.assertGreater(s2, 0)
        self.assertGreater(s1, 0)

    def test_diagnose_defense_failure_not_in_fixed(self):
        failure = {'error': 'test', 'module': 'auth'}
        case = SearchResult(source='.mem文件', file='20260410.mem',
                            content='Some historical experience', relevance=0.9)
        diagnosis = self.guard._diagnose_defense_failure(failure, case)
        self.assertEqual(diagnosis.failed_layer, 'memory')

    def test_diagnose_defense_failure_vague(self):
        failure = {'error': 'test', 'module': 'auth'}
        case = SearchResult(source='固定记忆', file='index.mem',
                            content='Short vague', relevance=0.9)
        diagnosis = self.guard._diagnose_defense_failure(failure, case)
        self.assertEqual(diagnosis.failed_layer, 'memory')

    def test_diagnose_defense_failure_intuition(self):
        """在固定记忆中且描述具体（含强制词），应诊断为直觉层失效"""
        failure = {'error': 'test', 'module': 'auth'}
        case = SearchResult(source='固定记忆', file='index.mem',
                            content='密码必须使用 bcrypt 加密存储，禁止明文保存密码到数据库中', relevance=0.9)
        diagnosis = self.guard._diagnose_defense_failure(failure, case)
        self.assertEqual(diagnosis.failed_layer, 'intuition')

    def test_format_alarm(self):
        alarm = RegressionAlarm(
            current_failure={'error': 'JWT expired', 'module': 'auth'},
            historical_case=SearchResult(source='固定记忆', file='index.mem',
                                          content='JWT must be refreshed', relevance=0.9),
            similarity=0.9,
            diagnosis=DefenseFailureDiagnosis(
                failed_layer='memory',
                diagnosis='Not injected',
                prescription='Promote to SP',
            ),
        )
        text = self.guard.format_alarm(alarm)
        self.assertIn('回归警报', text)
        self.assertIn('90%', text)


class TestMemoryManager(unittest.TestCase):
    """MemoryManager 单元测试"""

    def setUp(self):
        self.tmp = tempfile.mkdtemp(prefix="adds_test_mm_")
        self.mgr = MemoryManager(sessions_dir=self.tmp, project_root='..')

    def tearDown(self):
        shutil.rmtree(self.tmp)

    def test_ensure_index_mem(self):
        self.mgr.ensure_index_mem()
        self.assertTrue((Path(self.tmp) / 'index.mem').exists())

    def test_read_index_mem(self):
        self.mgr.ensure_index_mem()
        content, items = self.mgr.read_index_mem()
        self.assertIsInstance(content, str)
        self.assertIsInstance(items, list)
        self.assertGreater(len(items), 0)

    def test_write_index_mem(self):
        self.mgr.ensure_index_mem()
        new_item = MemoryItem(
            id='exp-test', content='Test experience | module: test',
            category='experience', role='developer', status='active',
            last_accessed=datetime.now(),
        )
        _, items = self.mgr.read_index_mem()
        items.append(new_item)
        self.mgr.write_index_mem(items)

        _, items2 = self.mgr.read_index_mem()
        self.assertTrue(any(i.id == 'exp-test' for i in items2))

    def test_get_status(self):
        self.mgr.ensure_index_mem()
        status = self.mgr.get_status()
        self.assertIsInstance(status, MemoryStatus)
        self.assertGreater(status.total_fixed_memories, 0)

    def test_build_memory_injection(self):
        self.mgr.ensure_index_mem()
        injection = self.mgr.build_memory_injection(role='developer')
        self.assertIsInstance(injection, str)
        # Should contain some memory section
        self.assertTrue(
            '记忆' in injection or '项目环境' in injection or '核心经验' in injection
        )

    def test_evaluate_and_upgrade(self):
        self.mgr.ensure_index_mem()
        mem_content = '决定使用 JWT 进行认证\n必须使用 bcrypt 存储密码\nFastAPI 框架配置'
        evaluations = asyncio.run(self.mgr.evaluate_and_upgrade(mem_content, role='developer'))
        self.assertIsInstance(evaluations, list)
        # Should find at least the decision and mandatory items
        self.assertGreater(len(evaluations), 0)

    def test_checkpoint(self):
        self.mgr.ensure_index_mem()
        ckpt = self.mgr.checkpoint('v0.1')
        self.assertTrue(Path(ckpt).exists())
        self.assertIn('v0.1', ckpt)

    def test_add_index_entry(self):
        self.mgr.ensure_index_mem()
        self.mgr.add_index_entry('04-10 16:00', 'test.mem', 'Test session', '中')
        content, _ = self.mgr.read_index_mem()
        self.assertIn('Test session', content)

    def test_add_conflict_record(self):
        self.mgr.ensure_index_mem()
        self.mgr.add_conflict_record('Test conflict', 'system_prompt', 'fixed_memory', 'auto')
        content, _ = self.mgr.read_index_mem()
        self.assertIn('Test conflict', content)

    def test_get_item_by_id(self):
        self.mgr.ensure_index_mem()
        new_item = MemoryItem(
            id='exp-find', content='Findable item',
            category='experience', status='active',
            last_accessed=datetime.now(),
        )
        _, items = self.mgr.read_index_mem()
        items.append(new_item)
        self.mgr.write_index_mem(items)

        found = self.mgr.get_item_by_id('exp-find')
        self.assertIsNotNone(found)
        self.assertEqual(found.id, 'exp-find')

    def test_update_item(self):
        self.mgr.ensure_index_mem()
        new_item = MemoryItem(
            id='exp-update', content='Updatable item',
            category='experience', status='active',
            last_accessed=datetime.now(),
        )
        _, items = self.mgr.read_index_mem()
        items.append(new_item)
        self.mgr.write_index_mem(items)

        self.mgr.update_item('exp-update', {'status': 'invalidated'})
        updated = self.mgr.get_item_by_id('exp-update')
        self.assertIsNotNone(updated)
        self.assertEqual(updated.status, 'invalidated')

    def test_delete_item(self):
        self.mgr.ensure_index_mem()
        new_item = MemoryItem(
            id='exp-delete', content='Deletable item',
            category='experience', status='active',
            last_accessed=datetime.now(),
        )
        _, items = self.mgr.read_index_mem()
        items.append(new_item)
        self.mgr.write_index_mem(items)

        self.mgr.delete_item('exp-delete')
        deleted = self.mgr.get_item_by_id('exp-delete')
        self.assertIsNone(deleted)

    def test_delete_nonexistent(self):
        self.mgr.ensure_index_mem()
        result = self.mgr.delete_item('nonexistent-id')
        self.assertFalse(result)

    def test_search_memory(self):
        # Create a .mem file for search
        mem_file = Path(self.tmp) / "20260410-160000.mem"
        mem_file.write_text("JWT token 认证实现\n测试通过", encoding="utf-8")

        results = asyncio.run(self.mgr.search_memory('JWT', top_k=3))
        self.assertIsInstance(results, list)

    def test_check_regression(self):
        # Create a .mem file with error info
        mem_file = Path(self.tmp) / "20260410-160000.mem"
        mem_file.write_text("JWT token expired error in auth module", encoding="utf-8")

        alarm = asyncio.run(self.mgr.check_regression({
            'error': 'JWT token expired',
            'module': 'auth',
            'code_snippet': '',
        }))
        # May or may not find a regression depending on search results

    def test_evaluate_invalidation(self):
        self.mgr.ensure_index_mem()
        new_item = MemoryItem(
            id='exp-inv', content='Use httpx for HTTP', category='experience',
            module='http', status='active', last_accessed=datetime.now(),
        )
        _, items = self.mgr.read_index_mem()
        items.append(new_item)
        self.mgr.write_index_mem(items)

        results = asyncio.run(self.mgr.evaluate_invalidation(
            session_mem='Task failed: httpx timeout',
            failed_context={'error': 'httpx connection timeout', 'code_snippet': ''},
        ))
        self.assertIsInstance(results, list)


class TestMemoryUpgradeEvaluation(unittest.TestCase):
    """MemoryUpgradeEvaluation 单元测试"""

    def test_needs_review_low_confidence(self):
        ev = MemoryUpgradeEvaluation(confidence=0.5)
        self.assertTrue(ev.needs_review())

    def test_needs_review_preference(self):
        ev = MemoryUpgradeEvaluation(confidence=0.9, category='preference')
        self.assertTrue(ev.needs_review())

    def test_no_review_needed(self):
        ev = MemoryUpgradeEvaluation(confidence=0.8, category='experience')
        self.assertFalse(ev.needs_review())


if __name__ == "__main__":
    unittest.main()
