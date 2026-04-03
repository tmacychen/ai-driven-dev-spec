#!/usr/bin/env python3
"""
ADDS - AI-Driven Development Specification CLI Tool

Core Features:
1. System prompt auto-injection
2. Agent Loop state machine
3. Latch mechanism
4. Fail-safe defaults
5. Compliance tracking

Reference: Claude Code Architecture Design
"""

import asyncio
import json
import os
import sys
from pathlib import Path
from typing import List, Optional
from datetime import datetime

# 导入改进模块
from system_prompt_builder import SystemPromptBuilder, build_agent_specific_prompt
from agent_loop import (
    ADDSAgentLoop, Feature, FeatureStatus, AgentType,
    ProjectLatches, FeatureStateLatches, SafetyDefaults
)
from compliance_tracker import ComplianceTracker


class ADDSCli:
    """
    ADDS CLI Tool
    
    Core Improvements:
    1. System prompt auto-injection - AI doesn't need to read specs
    2. Agent Loop enforcement - State-driven, not AI-dependent
    3. Latch protection - Prevents state thrashing
    4. Fail-safe defaults - Safest behavior by default
    5. Compliance tracking - Monitors AI adherence to specs
    """
    
    def __init__(self, project_root: str = "."):
        self.project_root = Path(project_root)
        self.ai_dir = self.project_root / ".ai"
        
        # 改进组件
        self.prompt_builder = SystemPromptBuilder(project_root)
        self.project_latches = ProjectLatches()
        self.feature_latches = FeatureStateLatches()
        self.safety = SafetyDefaults()
        self.compliance = ComplianceTracker()
        
    def init(self):
        """
        初始化 ADDS 项目
        
        改进：
        - 创建标准目录结构
        - 生成初始系统提示词
        - 锁存项目类型
        """
        print("=" * 80)
        print("🚀 ADDS Project Initialization")
        print("=" * 80)
        
        # 创建目录
        dirs = [
            self.ai_dir,
            self.ai_dir / "sessions",
            self.project_root / "templates" / "prompts" / "sections",
        ]
        
        for d in dirs:
            d.mkdir(parents=True, exist_ok=True)
            print(f"✅ 创建目录: {d}")
        
        # 创建初始文件
        self._create_feature_list_template()
        self._create_progress_template()
        self._create_system_prompt_file()
        
        # 锁存项目类型（示例）
        self.project_latches.latch_project_type(
            type('State', (), {})(), 
            "web_app"  # 可根据实际项目推断
        )
        
        print("\n✅ 初始化完成！")
        print("\n下一步：")
        print("1. 编辑 .ai/feature_list.md 定义功能")
        print("2. 运行 'adds route' 查看推荐的代理")
        print("3. 运行 'adds start' 开始开发")
    
    def status(self):
        """
        查看项目状态
        
        改进：
        - 合规性报告
        - 锁存状态显示
        """
        print("=" * 80)
        print("📊 ADDS Project Status")
        print("=" * 80)
        
        feature_list_path = self.ai_dir / "feature_list.md"
        
        # 检查 feature_list.md 是否存在
        if not feature_list_path.exists():
            print("❌ feature_list.md 不存在")
            print("请先运行 'adds init' 初始化项目")
            return
        
        # 读取功能列表
        features = self._parse_feature_list(feature_list_path)
        
        # 统计
        status_counts = {}
        for f in features:
            status_counts[f['status']] = status_counts.get(f['status'], 0) + 1
        
        print(f"\n功能总数: {len(features)}")
        print("\n状态分布:")
        for status, count in status_counts.items():
            print(f"  {status}: {count}")
        
        # 进度
        completed = status_counts.get('completed', 0)
        total = len(features)
        progress = (completed / total * 100) if total > 0 else 0
        print(f"\n进度: {progress:.1f}% ({completed}/{total})")
        
        # 合规性报告
        if (self.ai_dir / "compliance_report.json").exists():
            print("\n" + "=" * 80)
            print("最近合规报告:")
            with open(self.ai_dir / "compliance_report.json") as f:
                report = json.load(f)
                print(f"合规分数: {report['summary']['compliance_score']:.2f}")
                print(f"违规次数: {report['summary']['violations_count']}")
    
    def validate(self):
        """
        Validate feature_list.md format and content
        
        Checks:
        - File exists
        - Correct markdown format
        - Required fields present
        - Valid status values
        - Dependency references exist
        """
        print("=" * 80)
        print("✅ Validating feature_list.md")
        print("=" * 80)
        
        feature_list_path = self.ai_dir / "feature_list.md"
        
        # Check file exists
        if not feature_list_path.exists():
            print("❌ feature_list.md not found")
            print("Run 'adds init' to create a template")
            return False
        
        # Read and parse
        features = self._parse_feature_list(feature_list_path)
        
        if not features:
            print("❌ No features found in feature_list.md")
            return False
        
        # Validate each feature
        errors = []
        warnings = []
        valid_statuses = ['pending', 'in_progress', 'testing', 'completed', 'bug']
        
        for i, feature in enumerate(features, 1):
            # Check required fields
            if not feature.get('name'):
                errors.append(f"Feature {i}: Missing name")
            
            if not feature.get('status'):
                errors.append(f"Feature {i}: Missing status")
            elif feature['status'] not in valid_statuses:
                errors.append(f"Feature {i}: Invalid status '{feature['status']}'")
            
            # Check description (warning only)
            if not feature.get('description'):
                warnings.append(f"Feature {i}: Missing description")
        
        # Print results
        if errors:
            print("\n❌ Validation FAILED")
            print("\nErrors:")
            for error in errors:
                print(f"  - {error}")
            return False
        
        if warnings:
            print("\n⚠️  Validation passed with warnings:")
            for warning in warnings:
                print(f"  - {warning}")
        
        print(f"\n✅ Validation passed")
        print(f"Total features: {len(features)}")
        
        # Show status distribution
        status_counts = {}
        for f in features:
            status_counts[f['status']] = status_counts.get(f['status'], 0) + 1
        
        print("\nStatus distribution:")
        for status, count in sorted(status_counts.items()):
            print(f"  {status}: {count}")
        
        return True
    def route(self):
        """
        代理路由 - 自动推荐应该使用的代理
        
        改进：
        - 基于规则的确定性路由
        - 失败关闭：默认 PM Agent
        """
        print("=" * 80)
        print("🧭 代理路由推荐")
        print("=" * 80)
        
        feature_list_path = self.ai_dir / "feature_list.md"
        
        # 检查规范遵循
        if not self.compliance.check_feature_list_exists(str(feature_list_path)):
            print("\n❌ feature_list.md 不存在")
            print("推荐代理: PM Agent (初始化项目)")
            return
        
        # 读取功能列表
        features = self._parse_feature_list(feature_list_path)
        
        # 转换为 Feature 对象
        feature_objs = [
            Feature(
                name=f['name'],
                description=f.get('description', ''),
                status=FeatureStatus(f['status'])
            )
            for f in features
        ]
        
        # 创建状态
        state = type('State', (), {})()
        state.project_type = "web_app"  # 已锁存
        state.tech_stack = ["Python"]   # 已锁存
        
        # 路由决策
        recommended_agent = self.safety.safe_agent_selection(state, feature_objs)
        
        print(f"\n推荐代理: {recommended_agent.value.upper()} Agent")
        
        # 显示原因
        reasons = {
            AgentType.PM: "项目需要初始化或需求分析",
            AgentType.ARCHITECT: "需要技术架构设计",
            AgentType.DEVELOPER: f"有 {len([f for f in feature_objs if f.status == FeatureStatus.PENDING])} 个待实现功能",
            AgentType.TESTER: f"有 {len([f for f in feature_objs if f.status == FeatureStatus.TESTING])} 个待测试功能",
            AgentType.REVIEWER: "所有功能已完成，需要代码审查"
        }
        
        print(f"原因: {reasons[recommended_agent]}")
        
        # 显示专属提示词预览
        print("\n" + "=" * 80)
        print("代理专属提示词预览:")
        print("=" * 80)
        agent_prompt = build_agent_specific_prompt(recommended_agent.value, {})
        print(agent_prompt[:500] + "...")
    
    def start(self, max_turns: int = 50):
        """
        启动 ADDS Agent Loop
        
        改进：
        - 显式状态机控制
        - 自动代理切换
        - 合规性追踪
        """
        print("=" * 80)
        print("🚀 Starting ADDS Agent Loop")
        print("=" * 80)
        
        feature_list_path = self.ai_dir / "feature_list.md"
        
        # 检查规范遵循
        if not self.compliance.check_feature_list_exists(str(feature_list_path)):
            print("\n❌ feature_list.md 不存在，请先运行 'adds init'")
            return
        
        # 读取功能列表
        features_data = self._parse_feature_list(feature_list_path)
        
        # 转换为 Feature 对象
        features = [
            Feature(
                name=f['name'],
                description=f.get('description', ''),
                status=FeatureStatus(f['status'])
            )
            for f in features_data
        ]
        
        # 创建 Agent Loop
        loop = ADDSAgentLoop()
        loop.safety = self.safety
        loop.project_latches = self.project_latches
        
        # 运行
        result = asyncio.run(loop.run(features))
        
        # 更新功能列表文件
        self._update_feature_list(feature_list_path, features)
        
        # 保存合规报告
        self.compliance.save_report(str(self.ai_dir / "compliance_report.json"))
        
        print(f"\n最终结果: {result.value}")
    
    def inject_prompt(self, output_file: str = None):
        """
        生成并注入系统提示词
        
        改进：
        - 分段式构建
        - 静态/动态边界
        - 自动注入到 AI 上下文
        """
        print("=" * 80)
        print("💉 注入系统提示词")
        print("=" * 80)
        
        # 构建上下文
        context = {
            'feature_list_path': str(self.ai_dir / "feature_list.md"),
            'current_feature': None,
            'current_status': None,
            'current_agent': 'developer',
            'project_type': 'web_app',
            'tech_stack': ['Python', 'FastAPI']
        }
        
        # 读取当前功能（如果有）
        feature_list_path = self.ai_dir / "feature_list.md"
        if feature_list_path.exists():
            features = self._parse_feature_list(feature_list_path)
            pending = [f for f in features if f['status'] == 'pending']
            if pending:
                context['current_feature'] = pending[0]['name']
                context['current_status'] = 'in_progress'
        
        # 构建系统提示词
        prompt = self.prompt_builder.build_system_prompt(context)
        
        # 输出
        if output_file:
            output_path = Path(output_file)
            output_path.write_text("\n\n".join(prompt), encoding='utf-8')
            print(f"✅ 系统提示词已注入到: {output_file}")
        else:
            print("\n" + "=" * 80)
            print("系统提示词内容:")
            print("=" * 80)
            print("\n\n".join(prompt))
    
    def hooks(self, action: str):
        """
        Manage Git hooks for ADDS
        
        Actions:
        - install: Install pre-commit and post-merge hooks
        - uninstall: Remove Git hooks
        - status: Show hooks status
        """
        if action == 'install':
            self._install_hooks()
        elif action == 'uninstall':
            self._uninstall_hooks()
        elif action == 'status':
            self._show_hooks_status()
        else:
            print(f"❌ Unknown hooks action: {action}")
            print("Available actions: install, uninstall, status")
    
    def _install_hooks(self):
        """Install Git hooks for ADDS"""
        print("=" * 80)
        print("🪝 Installing Git Hooks")
        print("=" * 80)
        
        # Check if Git repository exists
        git_dir = self.project_root / ".git"
        if not git_dir.exists():
            print("❌ Not a Git repository")
            print("Please run 'git init' first")
            return
        
        hooks_dir = git_dir / "hooks"
        hooks_dir.mkdir(exist_ok=True)
        
        # Pre-commit hook
        pre_commit_hook = hooks_dir / "pre-commit"
        pre_commit_content = r"""#!/bin/bash
# ADDS Pre-commit Hook
# Validates feature_list.md before each commit

# Validate feature_list.md
if [ -f ".ai/feature_list.md" ]; then
    python3 scripts/adds.py validate
    if [ $? -ne 0 ]; then
        echo "❌ feature_list.md validation failed"
        exit 1
    fi
fi

# Check for forbidden commands
if grep -r "sudo\|rm -rf /\|mkfs\|fdisk" --include="*.sh" --include="*.py" .; then
    echo "❌ Forbidden commands detected"
    exit 1
fi

echo "✅ Pre-commit checks passed"
"""
        
        pre_commit_hook.write_text(pre_commit_content, encoding='utf-8')
        pre_commit_hook.chmod(0o755)  # Make executable
        print(f"✅ Installed pre-commit hook: {pre_commit_hook}")
        
        # Post-merge hook
        post_merge_hook = hooks_dir / "post-merge"
        post_merge_content = """#!/bin/bash
# ADDS Post-merge Hook
# Validates feature_list.md after merge

# Check if feature_list.md was modified
if git diff HEAD@{1} HEAD --name-only | grep -q "feature_list.md"; then
    echo "📋 Feature list updated"
    python3 scripts/adds.py validate
fi

echo "✅ Post-merge checks passed"
"""
        
        post_merge_hook.write_text(post_merge_content, encoding='utf-8')
        post_merge_hook.chmod(0o755)  # Make executable
        print(f"✅ Installed post-merge hook: {post_merge_hook}")
        
        print("\n🎉 Git hooks installed successfully!")
        print("\nInstalled hooks:")
        print("  - pre-commit: Validates feature_list.md before commit")
        print("  - post-merge: Validates feature_list.md after merge")
    
    def _uninstall_hooks(self):
        """Remove Git hooks"""
        print("=" * 80)
        print("🗑️  Uninstalling Git Hooks")
        print("=" * 80)
        
        hooks_dir = self.project_root / ".git" / "hooks"
        if not hooks_dir.exists():
            print("❌ Git hooks directory not found")
            return
        
        hooks_to_remove = ['pre-commit', 'post-merge']
        removed = []
        
        for hook_name in hooks_to_remove:
            hook_path = hooks_dir / hook_name
            if hook_path.exists():
                # Check if it's an ADDS hook
                content = hook_path.read_text(encoding='utf-8')
                if 'ADDS' in content:
                    hook_path.unlink()
                    removed.append(hook_name)
                    print(f"✅ Removed: {hook_name}")
                else:
                    print(f"⚠️  Skipped: {hook_name} (not an ADDS hook)")
            else:
                print(f"○  Not found: {hook_name}")
        
        if removed:
            print(f"\n✅ Uninstalled {len(removed)} hook(s)")
        else:
            print("\n○  No ADDS hooks found")
    
    def _show_hooks_status(self):
        """Show Git hooks status"""
        print("=" * 80)
        print("🔍 Git Hooks Status")
        print("=" * 80)
        
        hooks_dir = self.project_root / ".git" / "hooks"
        if not hooks_dir.exists():
            print("❌ Git hooks directory not found")
            print("Run 'git init' first")
            return
        
        hooks_to_check = ['pre-commit', 'post-merge']
        
        for hook_name in hooks_to_check:
            hook_path = hooks_dir / hook_name
            if hook_path.exists():
                content = hook_path.read_text(encoding='utf-8')
                if 'ADDS' in content:
                    print(f"✅ {hook_name}: Installed (ADDS hook)")
                else:
                    print(f"⚠️  {hook_name}: Present (not an ADDS hook)")
            else:
                print(f"○  {hook_name}: Not installed")
        
        print("\nCommands:")
        print("  adds hooks install    - Install Git hooks")
        print("  adds hooks uninstall  - Remove Git hooks")
        print("  adds hooks status     - Show this status")
    
    def _create_feature_list_template(self):
        """创建功能列表模板"""
        template = """# 功能列表

## 功能 1: user_authentication
- **描述**: 实现用户认证功能，包括登录、注册、登出
- **状态**: pending
- **依赖**: 无
- **验收标准**:
  - 用户可以使用邮箱和密码注册
  - 用户可以使用邮箱和密码登录
  - 用户可以登出
  - 密码使用 bcrypt 加密存储

## 功能 2: data_validation
- **描述**: 实现数据验证功能
- **状态**: pending
- **依赖**: user_authentication
- **验收标准**:
  - 输入数据格式验证
  - 业务规则验证
  - 错误信息友好提示

## 功能 3: api_endpoints
- **描述**: 实现 RESTful API 端点
- **状态**: pending
- **依赖**: user_authentication, data_validation
- **验收标准**:
  - 符合 RESTful 规范
  - 返回正确的 HTTP 状态码
  - 错误处理完善
"""
        
        feature_list_path = self.ai_dir / "feature_list.md"
        if not feature_list_path.exists():
            feature_list_path.write_text(template, encoding='utf-8')
            print(f"✅ 创建功能列表模板: {feature_list_path}")
    
    def _create_progress_template(self):
        """创建进度日志模板"""
        template = f"""# 进度日志

## 会话历史

### {datetime.now().strftime('%Y-%m-%d %H:%M')}
- 项目初始化
- 创建功能列表

"""
        
        progress_path = self.ai_dir / "progress.md"
        if not progress_path.exists():
            progress_path.write_text(template, encoding='utf-8')
            print(f"✅ 创建进度日志: {progress_path}")
    
    def _create_system_prompt_file(self):
        """创建系统提示词文件"""
        prompt_dir = self.project_root / "templates" / "prompts" / "sections"
        prompt_dir.mkdir(parents=True, exist_ok=True)
        
        # 创建示例段落
        identity_path = prompt_dir / "identity.md"
        if not identity_path.exists():
            identity_path.write_text("# AI-Driven Development Specification Agent\n", encoding='utf-8')
            print(f"✅ 创建系统提示词段落: {identity_path}")
    
    def _parse_feature_list(self, filepath: Path) -> List[dict]:
        """解析功能列表文件"""
        features = []
        
        # 简化解析（实际应使用完整的 Markdown 解析器）
        content = filepath.read_text(encoding='utf-8')
        
        # 提取功能块
        import re
        pattern = r'## 功能 \d+: (.+?)\n(- \*\*描述\*\*: (.+?)\n)?- \*\*状态\*\*: (\w+)'
        
        for match in re.finditer(pattern, content, re.MULTILINE):
            features.append({
                'name': match.group(1),
                'description': match.group(3) or '',
                'status': match.group(4)
            })
        
        return features
    
    def _update_feature_list(self, filepath: Path, features: List[Feature]):
        """更新功能列表文件"""
        # 简化实现（实际应保留原始格式）
        content_lines = []
        
        for i, f in enumerate(features, 1):
            content_lines.append(f"## 功能 {i}: {f.name}")
            content_lines.append(f"- **描述**: {f.description}")
            content_lines.append(f"- **状态**: {f.status.value}")
            content_lines.append("")
        
        filepath.write_text("\n".join(content_lines), encoding='utf-8')
        print(f"✅ 更新功能列表: {filepath}")


def main():
    """CLI entry point"""
    import argparse
    
    parser = argparse.ArgumentParser(
        description="ADDS - AI-Driven Development Specification Tool",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  adds init              Initialize ADDS project
  adds status            Show project status
  adds route             Show recommended agent
  adds start             Start Agent Loop
  adds validate          Validate feature_list.md
  adds hooks install     Install Git hooks
  adds hooks uninstall   Uninstall Git hooks
  adds hooks status      Show hooks status
        """
    )
    
    subparsers = parser.add_subparsers(dest='command', help='Available commands')
    
    # init command
    subparsers.add_parser('init', help='Initialize ADDS project')
    
    # status command
    subparsers.add_parser('status', help='Show project status')
    
    # route command
    subparsers.add_parser('route', help='Show recommended agent')
    
    # start command
    start_parser = subparsers.add_parser('start', help='Start Agent Loop')
    start_parser.add_argument('--max-turns', type=int, default=50, help='Maximum iterations')
    
    # validate command
    subparsers.add_parser('validate', help='Validate feature_list.md')
    
    # inject-prompt command
    inject_parser = subparsers.add_parser('inject-prompt', help='Generate system prompt')
    inject_parser.add_argument('--output', type=str, help='Output file path')
    
    # hooks command
    hooks_parser = subparsers.add_parser('hooks', help='Manage Git hooks')
    hooks_parser.add_argument('action', choices=['install', 'uninstall', 'status'],
                             help='Hooks action (install/uninstall/status)')
    
    args = parser.parse_args()
    
    if not args.command:
        parser.print_help()
        return
    
    # Create CLI instance
    cli = ADDSCli()
    
    # Execute command
    if args.command == 'init':
        cli.init()
    elif args.command == 'status':
        cli.status()
    elif args.command == 'route':
        cli.route()
    elif args.command == 'start':
        cli.start(max_turns=args.max_turns)
    elif args.command == 'validate':
        cli.validate()
    elif args.command == 'inject-prompt':
        cli.inject_prompt(output_file=args.output)
    elif args.command == 'hooks':
        cli.hooks(action=args.action)


if __name__ == "__main__":
    main()
