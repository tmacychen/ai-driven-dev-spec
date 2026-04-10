#!/usr/bin/env python3
"""
ADDS - AI-Driven Development Specification CLI Tool

核心功能：
1. 选择大模型（API/CLI/SDK）
2. 创建 Agent + 角色提示词
3. 交互式对话
"""

import argparse
import asyncio
import sys
from pathlib import Path
from typing import List

_SCRIPT_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(_SCRIPT_DIR))

from agent_loop import AgentLoop
from model import ModelFactory, ModelInterface


# 内置角色提示词
BUILTIN_ROLES = {
    "pm": "你是一个项目经理，等待接受我的任务",
    "architect": "你是一个架构师，专注于技术架构设计和技术选型",
    "developer": "你是一个开发者，专注于功能实现和代码编写",
    "tester": "你是一个测试工程师，专注于测试验证和质量保障",
    "reviewer": "你是一个代码审查员，专注于代码质量、安全和最佳实践",
}


class ADDSCli:
    """ADDS CLI Tool"""

    def __init__(self, project_root: str = "."):
        self.project_root = Path(project_root)
        self.ai_dir = self.project_root / ".ai"

    def start(self, role: str = "", non_interactive: bool = False):
        """
        启动 ADDS Agent 对话

        流程：
        1. 选择大模型
        2. 解析角色提示词（--role 或默认 PM）
        3. 进入交互对话
        """
        # 解析角色提示词
        if role in BUILTIN_ROLES:
            system_prompt = BUILTIN_ROLES[role]
            role_label = f"{role} (内置)"
        elif role:
            system_prompt = role
            role_label = "自定义"
        else:
            system_prompt = BUILTIN_ROLES["pm"]
            role_label = "pm (默认)"

        # 选择模型
        factory = ModelFactory(project_root=self.project_root)
        model = factory.select_model(interactive=not non_interactive)

        # 创建 Agent
        loop = AgentLoop(model=model, system_prompt=system_prompt)
        print(f"\n📋 角色设定: {role_label}")
        print(f"   提示词: {system_prompt}")

        # 运行交互对话
        try:
            turns = asyncio.run(loop.run())
            print(f"\n📊 本次对话: {turns} 轮")
        except KeyboardInterrupt:
            print("\n\n👋 强制退出")

    def list_roles(self):
        """列出内置角色"""
        print("=" * 60)
        print("📋 内置角色")
        print("=" * 60)
        for name, prompt in BUILTIN_ROLES.items():
            print(f"\n  {name:12s}  {prompt}")
        print(f"\n💡 用法: adds start --role {list(BUILTIN_ROLES.keys())[0]}")
        print(f"   或自定义: adds start --role \"你的自定义提示词\"")

    def status(self):
        """查看项目状态"""
        print("=" * 60)
        print("📊 ADDS Project Status")
        print("=" * 60)
        feature_list_path = self.ai_dir / "feature_list.md"
        if feature_list_path.exists():
            features = self._parse_feature_list(feature_list_path)
            print(f"\n功能总数: {len(features)}")
            if features:
                for f in features:
                    print(f"  - {f['name']}: {f['status']}")
        else:
            print("\n⚠️  feature_list.md 不存在")

    def init(self):
        """初始化 ADDS 项目"""
        print("=" * 60)
        print("🚀 ADDS Project Initialization")
        print("=" * 60)
        dirs = [self.ai_dir, self.ai_dir / "sessions"]
        for d in dirs:
            d.mkdir(parents=True, exist_ok=True)
            print(f"✅ 创建目录: {d}")

        scaffold_dir = Path(__file__).resolve().parent.parent / "templates" / "scaffold"
        files = [
            scaffold_dir / ".ai" / "feature_list.md",
            scaffold_dir / ".ai" / "progress.md",
            scaffold_dir / ".ai" / "architecture.md",
            scaffold_dir / "CORE_GUIDELINES.md",
        ]
        for src in files:
            if src.exists():
                dest = self.ai_dir / src.name
                if not dest.exists():
                    dest.write_text(src.read_text(encoding="utf-8"), encoding="utf-8")
                    print(f"✅ 创建: {dest}")

        print("\n✅ 初始化完成！")

    def _parse_feature_list(self, filepath: Path) -> List[dict]:
        """解析功能列表"""
        import re
        content = filepath.read_text(encoding="utf-8")
        pattern = r'## 功能 \d+: (.+?)\n(- \*\*描述\*\*: (.+?)\n)?- \*\*状态\*\*: (\w+)'
        return [
            {"name": m.group(1), "description": m.group(3) or "", "status": m.group(4)}
            for m in re.finditer(pattern, content, re.MULTILINE)
        ]


def main():
    """CLI 入口"""
    ADDS_VERSION = "3.1.0"

    parser = argparse.ArgumentParser(
        description="ADDS - AI-Driven Development Specification Tool",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  adds start                        启动 PM Agent 对话（默认）
  adds start --role developer       启动开发者 Agent
  adds start --role "你是Rust专家"   自定义角色提示词
  adds start --non-interactive      非交互式选择模型
  adds list-roles                   列出内置角色
  adds init                         初始化项目
  adds status                       查看项目状态
        """
    )

    parser.add_argument("--version", action="version", version=f"ADDS v{ADDS_VERSION}")

    subparsers = parser.add_subparsers(dest="command", help="可用命令")

    # start command
    start_parser = subparsers.add_parser("start", help="启动 Agent 对话")
    start_parser.add_argument("--role", type=str, default="",
                              help="角色提示词（内置名如 pm/developer，或自定义文本）")
    start_parser.add_argument("--non-interactive", action="store_true",
                              help="非交互式模型选择（自动选第一个）")

    # list-roles command
    subparsers.add_parser("list-roles", help="列出内置角色")

    # init command
    subparsers.add_parser("init", help="初始化 ADDS 项目")

    # status command
    subparsers.add_parser("status", help="查看项目状态")

    args = parser.parse_args()

    if not args.command:
        parser.print_help()
        return

    cli = ADDSCli()

    if args.command == "start":
        cli.start(role=args.role, non_interactive=args.non_interactive)
    elif args.command == "list-roles":
        cli.list_roles()
    elif args.command == "init":
        cli.init()
    elif args.command == "status":
        cli.status()


if __name__ == "__main__":
    main()
