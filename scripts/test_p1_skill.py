#!/usr/bin/env python3
"""
P1 技能渐进式披露 — 功能测试

测试场景：
1. 技能注册与管理
2. Level 0 索引注入
3. Level 1 按需加载
4. Level 2 参考文件
5. 技能匹配
6. 与 SkillGenerator 导入
7. System Prompt 集成
8. CLI 子命令
9. 使用统计
10. 持久化与缓存
"""

import json
import shutil
import sys
import tempfile
from pathlib import Path

# 添加 scripts 到 path
sys.path.insert(0, str(Path(__file__).parent))

from skill_manager import (
    SkillManager, SkillMeta, SkillDetail, SkillFile,
    create_skill_manager,
)


class TestSkillRegistration:
    """场景 1: 技能注册与管理"""

    def setup_method(self):
        self.tmpdir = tempfile.mkdtemp()
        self.mgr = SkillManager(project_root=self.tmpdir)

    def teardown_method(self):
        shutil.rmtree(self.tmpdir, ignore_errors=True)

    def test_register_basic(self):
        """基本注册"""
        ok = self.mgr.register_skill(
            name="test-skill",
            description="A test skill",
            category="tool",
            provider="test",
        )
        assert ok is True
        metas = self.mgr.skills_list()
        assert len(metas) == 1
        assert metas[0].name == "test-skill"
        assert metas[0].description == "A test skill"

    def test_register_with_details(self):
        """带 Level 1 详情注册"""
        ok = self.mgr.register_skill(
            name="detailed-skill",
            description="A detailed skill",
            trigger="当需要测试时",
            command="test {input}",
            examples=["test example1", "test example2"],
        )
        assert ok is True
        detail = self.mgr.skill_view("detailed-skill")
        assert detail is not None
        assert detail.trigger == "当需要测试时"
        assert detail.command == "test {input}"
        assert len(detail.examples) == 2

    def test_register_duplicate_updates(self):
        """重复注册更新"""
        self.mgr.register_skill(name="dup", description="v1")
        self.mgr.register_skill(name="dup", description="v2-updated")
        metas = self.mgr.skills_list()
        assert len(metas) == 1
        assert metas[0].description == "v2-updated"

    def test_delete_skill(self):
        """删除技能"""
        self.mgr.register_skill(name="to-delete", description="delete me")
        assert self.mgr.delete_skill("to-delete") is True
        assert len(self.mgr.skills_list()) == 0
        assert self.mgr.delete_skill("nonexist") is False


class TestLevel0Index:
    """场景 2: Level 0 索引注入"""

    def setup_method(self):
        self.tmpdir = tempfile.mkdtemp()
        self.mgr = SkillManager(project_root=self.tmpdir)

    def teardown_method(self):
        shutil.rmtree(self.tmpdir, ignore_errors=True)

    def test_empty_index(self):
        """空技能库"""
        section = self.mgr.build_level0_section()
        assert section == ""

    def test_index_format(self):
        """索引格式验证"""
        self.mgr.register_skill(name="s1", description="desc1", category="tool", tags=["a", "b"])
        self.mgr.register_skill(name="s2", description="desc2", category="pattern")
        section = self.mgr.build_level0_section()
        assert "## 可用技能（Level 0 索引）" in section
        assert "[tool] s1: desc1" in section
        assert "[pattern] s2: desc2" in section
        assert "skill_view" in section

    def test_index_grouped_by_category(self):
        """按类别分组"""
        self.mgr.register_skill(name="a1", description="", category="tool")
        self.mgr.register_skill(name="b1", description="", category="domain")
        self.mgr.register_skill(name="a2", description="", category="tool")
        section = self.mgr.build_level0_section()
        # domain 出现在 tool 之前（按字母排序）
        domain_pos = section.find("### domain")
        tool_pos = section.find("### tool")
        assert domain_pos < tool_pos


class TestLevel1Detail:
    """场景 3: Level 1 按需加载"""

    def setup_method(self):
        self.tmpdir = tempfile.mkdtemp()
        self.mgr = SkillManager(project_root=self.tmpdir)

    def teardown_method(self):
        shutil.rmtree(self.tmpdir, ignore_errors=True)

    def test_view_existing(self):
        """查看已有技能详情"""
        self.mgr.register_skill(
            name="s1", description="d",
            trigger="触发条件", command="cmd",
            input_desc="输入", output_desc="输出",
            examples=["ex1"],
        )
        detail = self.mgr.skill_view("s1")
        assert detail is not None
        assert detail.trigger == "触发条件"

    def test_view_nonexistent(self):
        """查看不存在的技能"""
        detail = self.mgr.skill_view("nope")
        assert detail is None

    def test_level1_section(self):
        """Level 1 段落构建"""
        self.mgr.register_skill(
            name="s1", description="d",
            trigger="触发", command="cmd",
        )
        section = self.mgr.build_level1_section(["s1"])
        assert "## 技能详情（Level 1 — 按需加载）" in section
        assert "Skill: s1" in section

    def test_level1_section_empty(self):
        """空技能列表的 Level 1"""
        section = self.mgr.build_level1_section(["nope"])
        assert section == ""


class TestLevel2Files:
    """场景 4: Level 2 参考文件"""

    def setup_method(self):
        self.tmpdir = tempfile.mkdtemp()
        self.mgr = SkillManager(project_root=self.tmpdir)

    def teardown_method(self):
        shutil.rmtree(self.tmpdir, ignore_errors=True)

    def test_register_with_files(self):
        """注册带参考文件的技能"""
        self.mgr.register_skill(
            name="s1", description="d",
            ref_files=[
                {"path": "ref.md", "description": "Reference doc", "size_hint": "~200 token"},
            ],
        )
        files = self.mgr.skill_files("s1")
        assert len(files) == 1
        assert files[0].path == "ref.md"

    def test_load_nonexistent_file(self):
        """加载不存在的参考文件"""
        self.mgr.register_skill(name="s1", description="d")
        content = self.mgr.skill_load("s1", "nope.md")
        assert content is None

    def test_load_existing_file(self):
        """加载已存在的参考文件"""
        self.mgr.register_skill(name="s1", description="d")
        # 手动创建参考文件
        skill_dir = Path(self.tmpdir) / ".ai" / "memories" / "SKILLS" / "s1"
        skill_dir.mkdir(parents=True, exist_ok=True)
        ref_file = skill_dir / "guide.md"
        ref_file.write_text("# Guide\nContent here", encoding="utf-8")

        content = self.mgr.skill_load("s1", "guide.md")
        assert content is not None
        assert "Guide" in content


class TestSkillMatching:
    """场景 5: 技能匹配"""

    def setup_method(self):
        self.tmpdir = tempfile.mkdtemp()
        self.mgr = SkillManager(project_root=self.tmpdir)

    def teardown_method(self):
        shutil.rmtree(self.tmpdir, ignore_errors=True)

    def test_match_by_name(self):
        """按名称匹配"""
        self.mgr.register_skill(name="code-analysis", description="代码分析", tags=["code"])
        results = self.mgr.match_skills("code-analysis")
        assert len(results) >= 1
        assert results[0][0] == "code-analysis"
        assert results[0][1] >= 0.5  # 名称匹配得 0.5

    def test_match_by_description(self):
        """按描述匹配"""
        self.mgr.register_skill(name="s1", description="代码审查和bug检测")
        results = self.mgr.match_skills("代码审查")
        assert len(results) >= 1

    def test_match_by_tags(self):
        """按标签匹配"""
        self.mgr.register_skill(name="s1", description="d", tags=["testing", "pytest"])
        results = self.mgr.match_skills("testing")
        assert len(results) >= 1

    def test_suggest_skills(self):
        """推荐技能"""
        self.mgr.register_skill(name="code-review", description="代码审查", tags=["review"])
        self.mgr.register_skill(name="test-gen", description="测试生成", tags=["testing"])
        suggestions = self.mgr.suggest_skills("代码审查", top_k=1)
        assert len(suggestions) == 1
        assert suggestions[0] == "code-review"

    def test_no_match(self):
        """无匹配"""
        self.mgr.register_skill(name="s1", description="xyz")
        results = self.mgr.match_skills("完全无关的查询")
        assert len(results) == 0


class TestSystemPromptIntegration:
    """场景 7: System Prompt 集成"""

    def setup_method(self):
        self.tmpdir = tempfile.mkdtemp()

    def teardown_method(self):
        shutil.rmtree(self.tmpdir, ignore_errors=True)

    def test_skill_section_in_prompt(self):
        """技能段落注入 System Prompt"""
        from system_prompt_builder import SystemPromptBuilder

        builder = SystemPromptBuilder(project_root=self.tmpdir)
        mgr = SkillManager(project_root=self.tmpdir)
        mgr.register_skill(name="s1", description="Test skill", category="tool")

        context = {
            "skill_level0": mgr.build_level0_section(),
        }
        prompt = builder.build_system_prompt(context)
        # 检查技能段落是否被注入
        has_skill = any("可用技能" in s for s in prompt)
        assert has_skill

    def test_skill_level1_in_prompt(self):
        """Level 1 详情注入"""
        from system_prompt_builder import SystemPromptBuilder

        builder = SystemPromptBuilder(project_root=self.tmpdir)
        mgr = SkillManager(project_root=self.tmpdir)
        mgr.register_skill(
            name="s1", description="d",
            trigger="触发", command="cmd",
        )

        context = {
            "skill_level1": mgr.build_level1_section(["s1"]),
        }
        prompt = builder.build_system_prompt(context)
        has_detail = any("技能详情" in s for s in prompt)
        assert has_detail


class TestUsageStats:
    """场景 9: 使用统计"""

    def setup_method(self):
        self.tmpdir = tempfile.mkdtemp()
        self.mgr = SkillManager(project_root=self.tmpdir)

    def teardown_method(self):
        shutil.rmtree(self.tmpdir, ignore_errors=True)

    def test_usage_recording(self):
        """使用记录"""
        self.mgr.register_skill(
            name="s1", description="d",
            trigger="t", command="c",
        )
        self.mgr.skill_view("s1")
        self.mgr.skill_view("s1")
        stats = self.mgr.get_usage_stats()
        assert stats.get("s1") == 2

    def test_status(self):
        """状态概览"""
        self.mgr.register_skill(name="s1", description="d", category="tool")
        self.mgr.register_skill(name="s2", description="d", category="pattern")
        status = self.mgr.get_status()
        assert status["total_skills"] == 2
        assert "tool" in status["categories"]
        assert "pattern" in status["categories"]


class TestPersistence:
    """场景 10: 持久化与缓存"""

    def setup_method(self):
        self.tmpdir = tempfile.mkdtemp()

    def teardown_method(self):
        shutil.rmtree(self.tmpdir, ignore_errors=True)

    def test_registry_persistence(self):
        """注册表持久化"""
        mgr1 = SkillManager(project_root=self.tmpdir)
        mgr1.register_skill(name="s1", description="persistent skill", category="tool")

        # 重新创建管理器，应该能加载
        mgr2 = SkillManager(project_root=self.tmpdir)
        metas = mgr2.skills_list()
        assert len(metas) == 1
        assert metas[0].name == "s1"
        assert metas[0].description == "persistent skill"

    def test_detail_persistence(self):
        """详情持久化"""
        mgr1 = SkillManager(project_root=self.tmpdir)
        mgr1.register_skill(
            name="s1", description="d",
            trigger="触发", command="cmd",
            examples=["ex1"],
        )

        # 重新创建管理器
        mgr2 = SkillManager(project_root=self.tmpdir)
        detail = mgr2.skill_view("s1")
        assert detail is not None
        assert detail.trigger == "触发"
        assert detail.command == "cmd"


class TestSkillMetaIndexLine:
    """SkillMeta.to_index_line 格式测试"""

    def test_basic(self):
        meta = SkillMeta(name="test", description="A test")
        line = meta.to_index_line()
        assert "[general] test: A test" in line

    def test_with_tags(self):
        meta = SkillMeta(name="test", description="D", tags=["a", "b"])
        line = meta.to_index_line()
        assert "tags=a,b" in line

    def test_with_provider(self):
        meta = SkillMeta(name="test", description="D", provider="codebuddy")
        line = meta.to_index_line()
        assert "provider=codebuddy" in line


class TestSkillDetailFormat:
    """SkillDetail.to_level1_text 格式测试"""

    def test_basic(self):
        detail = SkillDetail(name="test", trigger="触发条件", command="cmd")
        text = detail.to_level1_text()
        assert "### Skill: test" in text
        assert "**触发**: 触发条件" in text
        assert "**命令**: `cmd`" in text

    def test_with_examples(self):
        detail = SkillDetail(
            name="test", trigger="t", command="c",
            examples=["ex1", "ex2"],
        )
        text = detail.to_level1_text()
        assert "`ex1`" in text
        assert "`ex2`" in text


# ═══════════════════════════════════════════════════════════
# 运行所有测试
# ═══════════════════════════════════════════════════════════

def run_all_tests():
    """运行所有测试"""
    test_classes = [
        TestSkillRegistration,
        TestLevel0Index,
        TestLevel1Detail,
        TestLevel2Files,
        TestSkillMatching,
        TestSystemPromptIntegration,
        TestUsageStats,
        TestPersistence,
        TestSkillMetaIndexLine,
        TestSkillDetailFormat,
    ]

    total = 0
    passed = 0
    failed = 0

    for cls in test_classes:
        instance = cls()
        methods = [m for m in dir(instance) if m.startswith("test_")]

        for method_name in methods:
            total += 1
            try:
                if hasattr(instance, "setup_method"):
                    instance.setup_method()
                getattr(instance, method_name)()
                passed += 1
                print(f"  ✅ {cls.__name__}.{method_name}")
            except Exception as e:
                failed += 1
                print(f"  ❌ {cls.__name__}.{method_name}: {e}")
            finally:
                if hasattr(instance, "teardown_method"):
                    instance.teardown_method()

    print(f"\n{'=' * 60}")
    print(f"技能渐进式披露测试: {passed}/{total} 通过, {failed} 失败")
    print(f"{'=' * 60}")
    return failed == 0


if __name__ == "__main__":
    success = run_all_tests()
    sys.exit(0 if success else 1)
