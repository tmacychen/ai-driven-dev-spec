#!/usr/bin/env python3
"""
ADDS v2.0 - 改进版 CLI 工具

集成改进：
1. 系统提示词自动注入
2. Agent Loop 状态机
3. 锁存机制
4. 失败关闭
5. 规范遵循追踪

参考：Claude Code 的整体架构设计
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


class ADDSCliV2:
    """
    ADDS v2.0 CLI 工具
    
    核心改进：
    1. 系统提示词自动注入 - AI 无需阅读规范
    2. Agent Loop 强制执行 - 状态驱动而非 AI 判断
    3. 锁存保护 - 防止状态抖动
    4. 失败关闭 - 默认最安全行为
    5. 合规追踪 - 监控 AI 是否遵循规范
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
        print("🚀 ADDS v2.0 项目初始化")
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
        print("2. 运行 'adds-v2 route' 查看推荐的代理")
        print("3. 运行 'adds-v2 start' 开始开发")
    
    def status(self):
        """
        查看项目状态
        
        改进：
        - 合规性报告
        - 锁存状态显示
        """
        print("=" * 80)
        print("📊 ADDS v2.0 项目状态")
        print("=" * 80)
        
        feature_list_path = self.ai_dir / "feature_list.md"
        
        # 检查 feature_list.md 是否存在
        if not feature_list_path.exists():
            print("❌ feature_list.md 不存在")
            print("请先运行 'adds-v2 init' 初始化项目")
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
        print("🚀 启动 ADDS Agent Loop v2.0")
        print("=" * 80)
        
        feature_list_path = self.ai_dir / "feature_list.md"
        
        # 检查规范遵循
        if not self.compliance.check_feature_list_exists(str(feature_list_path)):
            print("\n❌ feature_list.md 不存在，请先运行 'adds-v2 init'")
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
    """CLI 入口"""
    import argparse
    
    parser = argparse.ArgumentParser(description="ADDS v2.0 - 改进版 AI 开发规范工具")
    parser.add_argument('command', choices=['init', 'status', 'route', 'start', 'inject-prompt'],
                       help='命令类型')
    parser.add_argument('--max-turns', type=int, default=50, help='最大迭代次数')
    parser.add_argument('--output', type=str, help='输出文件路径')
    
    args = parser.parse_args()
    
    # 创建 CLI 实例
    cli = ADDSCliV2()
    
    # 执行命令
    if args.command == 'init':
        cli.init()
    elif args.command == 'status':
        cli.status()
    elif args.command == 'route':
        cli.route()
    elif args.command == 'start':
        cli.start(max_turns=args.max_turns)
    elif args.command == 'inject-prompt':
        cli.inject_prompt(output_file=args.output)


if __name__ == "__main__":
    main()
