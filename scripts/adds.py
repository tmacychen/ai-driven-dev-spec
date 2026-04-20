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
import importlib
import logging
import subprocess
import sys
from pathlib import Path
from typing import List

_SCRIPT_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(_SCRIPT_DIR))

# 项目根目录
_PROJECT_ROOT = _SCRIPT_DIR.parent


# ═══════════════════════════════════════════════════════════════
# 自动激活项目 .venv
# 当 adds 命令通过 symlink 调用时，用的是系统 Python，
# 但 anthropic 等依赖装在 .venv 里。此处自动检测并重启。
# ═══════════════════════════════════════════════════════════════

def _in_venv() -> bool:
    """当前是否已在虚拟环境中"""
    return hasattr(sys, "real_prefix") or (
        hasattr(sys, "base_prefix") and sys.base_prefix != sys.prefix
    )


def _try_activate_venv() -> None:
    """如果不在 venv 中，但项目 .venv 存在，则用 venv Python 重启自己"""
    if _in_venv():
        return  # 已在 venv 中

    venv_python = _PROJECT_ROOT / ".venv" / "bin" / "python3"
    if not venv_python.exists():
        venv_python = _PROJECT_ROOT / ".venv" / "bin" / "python"
    if not venv_python.exists():
        return  # .venv 不存在，稍后由依赖检测引导安装

    # 用 venv 的 Python 重新执行本脚本
    os.execv(str(venv_python), [str(venv_python)] + sys.argv)


import os
_try_activate_venv()


# ═══════════════════════════════════════════════════════════════
# 依赖检测与安装引导
# ═══════════════════════════════════════════════════════════════

REQUIRED_PACKAGES = {
    "anthropic": "anthropic>=0.40.0",
    "rich": "rich>=13.0.0",
    "yaml": "pyyaml>=6.0",
    "prompt_toolkit": "prompt_toolkit>=3.0.0",
    "textual": "textual>=0.47.0",
}


def check_dependencies() -> bool:
    """检测依赖是否已安装，返回 True 表示全部就绪"""
    missing = {}
    for pkg, spec in REQUIRED_PACKAGES.items():
        try:
            importlib.import_module(pkg)
        except ImportError:
            missing[pkg] = spec

    if not missing:
        return True

    print("❌ 缺少以下 Python 依赖：\n")
    for pkg, spec in missing.items():
        print(f"   • {spec}")

    print("\n📦 请选择安装方式：\n")
    print("   方式一：项目虚拟环境（推荐）")
    print("   ─────────────────────────────")
    print("   python3 -m venv .venv")
    print("   source .venv/bin/activate        # Fish: source .venv/bin/activate.fish")
    print(f"   pip install {' '.join(missing.values())}")
    print()
    print("   方式二：一键安装（自动创建 venv + 安装依赖）")
    print("   ─────────────────────────────")
    print("   python3 scripts/adds.py install-deps")
    print()
    print("   方式三：全局安装")
    print("   ─────────────────────────────")
    print(f"   pip3 install {' '.join(missing.values())}")
    print()

    return False


def install_deps():
    """自动安装依赖：创建 venv + pip install"""
    project_root = _SCRIPT_DIR.parent
    venv_dir = project_root / ".venv"

    # 检测当前是否已在 venv 中
    in_venv = hasattr(sys, "real_prefix") or (
        hasattr(sys, "base_prefix") and sys.base_prefix != sys.prefix
    )

    if in_venv:
        # 已在虚拟环境中，直接安装
        print("📦 当前已在虚拟环境中，直接安装依赖...\n")
        _pip_install(sys.executable)
        return

    # 不在 venv 中，创建/使用项目 venv
    if not venv_dir.exists():
        print(f"📦 创建虚拟环境: {venv_dir}")
        subprocess.run([sys.executable, "-m", "venv", str(venv_dir)], check=True)
        print("✅ 虚拟环境创建成功\n")
    else:
        print(f"📦 使用已有虚拟环境: {venv_dir}\n")

    # 确定 venv 的 python 路径
    venv_python = venv_dir / "bin" / "python3"
    if not venv_python.exists():
        venv_python = venv_dir / "bin" / "python"

    _pip_install(str(venv_python))

    # 提示激活
    print("\n✅ 依赖安装完成！")
    print("\n💡 使用以下命令启动：")
    print(f"   source {venv_dir}/bin/activate")
    print("   adds start")
    print()
    print("   或直接用 venv 的 python：")
    print(f"   {venv_dir}/bin/python3 scripts/adds.py start")


def _pip_install(python_path: str):
    """执行 pip install，优先从 requirements.txt 读取"""
    req_file = _PROJECT_ROOT / "requirements.txt"
    if req_file.exists():
        print(f"📥 从 requirements.txt 安装依赖...\n")
        result = subprocess.run(
            [python_path, "-m", "pip", "install", "--upgrade", "-r", str(req_file)],
        )
    else:
        packages = list(REQUIRED_PACKAGES.values())
        print(f"📥 安装依赖: {' '.join(packages)}\n")
        result = subprocess.run(
            [python_path, "-m", "pip", "install", "--upgrade"] + packages,
        )
    if result.returncode != 0:
        print("\n❌ 安装失败，请尝试手动安装：")
        print(f"   {python_path} -m pip install -r requirements.txt")
        sys.exit(1)


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

    def start(self, role: str = "", non_interactive: bool = False, debug: bool = False,
              skin_name: str = "", perm_mode: str = "default", tui: bool = False):
        """
        启动 ADDS Agent 对话

        流程：
        1. 选择大模型
        2. 解析角色提示词（--role 或默认 PM）
        3. 进入交互对话（classic 模式）或 TUI 模式（--tui）
        """
        # 配置日志
        # 默认：日志完全静默，stdout/stderr 只输出正常交互信息
        # Debug：日志写文件，不影响交互界面
        if debug:
            log_dir = self.ai_dir / "logs"
            log_dir.mkdir(parents=True, exist_ok=True)
            log_file = log_dir / "adds-debug.log"
            logging.basicConfig(
                level=logging.DEBUG,
                format="%(asctime)s %(levelname)s [%(name)s] %(message)s",
                datefmt="%Y-%m-%d %H:%M:%S",
                filename=str(log_file),
                filemode="a",
            )
        else:
            # 默认模式：日志不输出到 stdout/stderr
            logging.basicConfig(level=logging.CRITICAL + 1, handlers=[logging.NullHandler()])

        # 延迟导入（依赖检查通过后才执行）
        from model import ModelFactory
        from skins import SkinConfig, load_skin, render_banner, create_console

        # 加载皮肤
        skin = load_skin(skin_name) if skin_name else SkinConfig({})

        # 选择模型
        factory = ModelFactory(project_root=self.project_root)
        model = factory.select_model(interactive=not non_interactive)

        # ── TUI 模式 ──────────────────────────────────────────────
        if tui:
            try:
                from tui.app import ADDSApp
            except ImportError:
                print("❌ TUI 模式需要 textual，请运行: pip install textual>=0.47.0")
                sys.exit(1)
            app = ADDSApp(
                model=model,
                project_root=str(self.project_root),
                skin=skin,
                perm_mode=perm_mode,
            )
            app.run()
            return

        # ── Classic 模式 ──────────────────────────────────────────
        from agent_loop import AgentLoop
        console = create_console()

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

        model_name = model.get_model_name()
        ctx_window = model.get_context_window()

        # 渲染 Banner
        render_banner(console, skin, model_name=model_name,
                      context_window=ctx_window, role=role_label)

        # 创建 Agent（P0-2: 传入 project_root 和 agent_role, P0-4: 传入 permission_mode）
        loop = AgentLoop(model=model, system_prompt=system_prompt,
                         console=console, skin=skin,
                         project_root=str(self.project_root),
                         agent_role=role or "pm",
                         feature="",
                         permission_mode=perm_mode)

        # 运行交互对话
        try:
            turns = asyncio.run(loop.run())
            goodbye = skin.branding("goodbye", "Goodbye!")
            console.print(f"\n📊 本次对话: [bold]{turns}[/] 轮")
            console.print(f"[dim]{goodbye}[/]")
        except KeyboardInterrupt:
            console.print("\n\n[bold red]👋 强制退出[/]")

    def list_roles(self):
        """列出内置角色"""
        print("=" * 60)
        print("📋 内置角色")
        print("=" * 60)
        for name, prompt in BUILTIN_ROLES.items():
            print(f"\n  {name:12s}  {prompt}")
        print(f"\n💡 用法: adds start --role {list(BUILTIN_ROLES.keys())[0]}")
        print(f"   或自定义: adds start --role \"你的自定义提示词\"")

    def list_skins(self, preview: bool = False):
        """列出可用皮肤主题"""
        try:
            from skins import (
                SkinConfig, load_skin, list_skins as get_skin_list,
                render_banner, create_console, ADDS_LOGO, ADDS_LOGO_COLORS,
            )
            from rich.text import Text
            from rich.align import Align
            from rich.table import Table
            from rich.panel import Panel
        except ImportError:
            print("⚠️  皮肤引擎需要 rich 和 pyyaml，请运行: adds install-deps")
            return

        console = create_console()

        # 收集所有皮肤：内置 + 用户目录
        builtin_skins_dir = str(_SCRIPT_DIR / "skins")
        builtin_skins = get_skin_list(builtin_skins_dir)
        user_skins = get_skin_list()  # ~/.adds/skins/

        all_skins = {}
        for name in builtin_skins:
            skin = load_skin(name, config_dir=builtin_skins_dir)
            all_skins[name] = (skin, "内置")
        for name in user_skins:
            if name not in all_skins:
                skin = load_skin(name)
                all_skins[name] = (skin, "自定义")

        # 默认主题（无 YAML 文件）
        all_skins["adds_default"] = (SkinConfig({}), "内置 (默认)")

        # 按名称排序
        sorted_skins = sorted(all_skins.items())

        # 列表
        t = Table(show_header=True, box=None, padding=(0, 2))
        t.add_column("名称", style="bold #FFD700", width=20)
        t.add_column("来源", style="#4dd0e1", width=14)
        t.add_column("描述", style="#FFF8DC")

        for name, (skin, source) in sorted_skins:
            t.add_row(name, source, skin.description or "-")

        console.print(Panel(
            t,
            title="[bold #FFD700]🎨 可用皮肤主题[/]",
            border_style="#CD7F32",
            padding=(0, 1),
        ))
        console.print("\n[dim #B8860B]用法: adds start --skin adds_cyberpunk[/]")

        # 预览模式
        if preview:
            console.print()
            for name, (skin, source) in sorted_skins:
                console.rule(f"[bold #FFD700]{name}[/]")
                render_banner(console, skin, model_name="Demo-Model",
                             context_window=128000, role="pm")
                console.print()

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

    def validate(self):
        """校验 feature_list.md 格式"""
        feature_list_path = self.ai_dir / "feature_list.md"
        if not feature_list_path.exists():
            print("⚠️  feature_list.md 不存在，跳过校验")
            return True
        try:
            features = self._parse_feature_list(feature_list_path)
            if not features:
                print("⚠️  feature_list.md 中未找到功能定义")
                return False
            for f in features:
                if not f["name"] or not f["status"]:
                    print(f"❌ 功能定义不完整: {f}")
                    return False
            print(f"✅ feature_list.md 校验通过 ({len(features)} 个功能)")
            return True
        except Exception as e:
            print(f"❌ feature_list.md 解析失败: {e}")
            return False

    def init(self):
        """初始化 ADDS 项目"""
        print("=" * 60)
        print("🚀 ADDS Project Initialization")
        print("=" * 60)
        dirs = [self.ai_dir, self.ai_dir / "sessions", self.ai_dir / "memories"]
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

    def session_command(self, args):
        """P0-2: Session 管理子命令"""
        from session_manager import SessionManager

        sessions_dir = str(self.ai_dir / "sessions")
        mgr = SessionManager(sessions_dir=sessions_dir)

        if not args.session_command or args.session_command == "list":
            sessions = mgr.list_sessions()
            if not sessions:
                print("📭 暂无 Session 记录")
                return
            print("=" * 70)
            print("📋 Session 列表")
            print("=" * 70)
            for s in sessions:
                if "error" in s:
                    print(f"  ❌ {s['session_id']}: {s['error']}")
                else:
                    status_icon = "🟢" if s.get("status") == "active" else "📦"
                    print(f"  {status_icon} {s['session_id']}  agent={s.get('agent', '?')}  "
                          f"feature={s.get('feature', '?')}  status={s.get('status', '?')}")
            print()

        elif args.session_command == "restore":
            session_id = args.session_id
            try:
                path = mgr.restore_session(session_id)
                print(f"✅ Session 已恢复: {session_id}")
                print(f"   文件: {path}")
            except FileNotFoundError as e:
                print(f"❌ 恢复失败: {e}")

        elif args.session_command == "logs":
            session_id = args.session_id
            logs = mgr.list_logs(session_id)
            if not logs:
                print(f"📭 Session {session_id} 无 .log 文件")
            else:
                print(f"📋 Session {session_id} 的 .log 文件:")
                for log in logs:
                    print(f"  📄 {log}")

    def perm_command(self, args):
        """P0-4: 权限管理子命令"""
        from permission_manager import PermissionManager

        pm = PermissionManager(project_root=str(self.project_root))

        if not args.perm_command or args.perm_command == "status":
            stats = pm.get_stats()
            print("=" * 50)
            print("🔒 权限状态")
            print("=" * 50)
            print(f"  模式: {stats['mode']}")
            print(f"  检查次数: {stats['total_checks']}")
            print(f"  允许/确认/拒绝: {stats['allowed']}/{stats['asked']}/{stats['denied']}")
            if stats['cooldown_tools']:
                print(f"  冷却中: {', '.join(stats['cooldown_tools'])}")
            print()
            print("  模式说明:")
            print("    default  — 敏感操作逐一确认（推荐）")
            print("    plan     — 只能读不能写（探索阶段）")
            print("    auto     — AI 分类器自动决策（高级）")
            print("    bypass   — 所有操作自动放行（危险）")

        elif args.perm_command == "rules":
            print("=" * 50)
            print("📋 权限规则")
            print("=" * 50)
            for level_name, level in [("allow", "允许"), ("ask", "确认"), ("deny", "拒绝")]:
                from permission_manager import PermissionLevel
                rules = pm._rules[PermissionLevel(level_name)]
                if rules:
                    print(f"\n  [{level}] ({len(rules)} 条)")
                    for pattern, source in rules:
                        print(f"    {pattern:30s}  ← {source}")

        elif args.perm_command == "mode":
            new_mode = args.mode
            pm.set_mode(new_mode)
            if new_mode == "bypass":
                print("⚠️  bypass 模式已启用！所有操作将自动放行，请谨慎使用！")
            print(f"✅ 权限模式已切换为: {new_mode}")

    def mem_command(self, args):
        """P0-3: 记忆管理子命令"""
        from memory_cli import handle_mem_command
        handle_mem_command(args, project_root=str(self.project_root))


def main():
    """CLI 入口"""
    ADDS_VERSION = "3.1.0"

    parser = argparse.ArgumentParser(
        description="ADDS - AI-Driven Development Specification Tool",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  adds start                        启动 PM Agent 对话（默认）
  adds start --tui                  启动 TUI 模式（多 Agent 工作区）
  adds start --role developer       启动开发者 Agent
  adds start --role "你是Rust专家"   自定义角色提示词
  adds start --non-interactive      非交互式选择模型
  adds start --skin adds_cyberpunk  使用赛博朋克皮肤
  adds list-roles                   列出内置角色
  adds list-skins                   列出可用皮肤主题
  adds list-skins --preview         预览每个皮肤效果
  adds init                         初始化项目
  adds status                       查看项目状态
  adds validate                   校验 feature_list.md
  adds install-deps                 安装 Python 依赖
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
    start_parser.add_argument("--debug", action="store_true",
                              help="启用 debug 日志，输出到 .ai/logs/adds-debug.log")
    start_parser.add_argument("--skin", type=str, default="",
                              help="皮肤名称（如 adds_cyberpunk）")
    start_parser.add_argument("--perm", type=str, default="default",
                              choices=["default", "plan", "auto", "bypass"],
                              help="权限模式: default(推荐)/plan(只读)/auto(AI决策)/bypass(危险)")
    start_parser.add_argument("--tui", action="store_true",
                              help="启动 TUI 模式（多 Agent 工作区）")

    # list-roles command
    subparsers.add_parser("list-roles", help="列出内置角色")

    # list-skins command
    list_skins_parser = subparsers.add_parser("list-skins", help="列出可用皮肤主题")
    list_skins_parser.add_argument("--preview", action="store_true",
                                   help="预览每个主题的 Banner")

    # init command
    subparsers.add_parser("init", help="初始化 ADDS 项目")

    # status command
    subparsers.add_parser("status", help="查看项目状态")

    # validate command
    subparsers.add_parser("validate", help="校验 feature_list.md 格式")

    # install-deps command
    subparsers.add_parser("install-deps", help="安装 Python 依赖（自动创建 venv）")

    # session command (P0-2)
    session_parser = subparsers.add_parser("session", help="Session 管理（P0-2）")
    session_sub = session_parser.add_subparsers(dest="session_command")
    session_sub.add_parser("list", help="列出所有 Session")
    session_sub.add_parser("status", help="显示当前 Session 状态")
    session_restore = session_sub.add_parser("restore", help="从 .mem 恢复 Session")
    session_restore.add_argument("session_id", type=str, help="Session ID")
    session_logs = session_sub.add_parser("logs", help="查看 Session 的 .log 文件")
    session_logs.add_argument("session_id", type=str, help="Session ID")

    # mem command (P0-3)
    from memory_cli import add_mem_subparser
    add_mem_subparser(subparsers)

    # skill command (P1)
    from skill_manager import add_skill_subparser
    add_skill_subparser(subparsers)

    # schedule command (P2-1)
    from scheduler import add_schedule_subparser
    add_schedule_subparser(subparsers)

    # executor command (P2-2)
    from executor_backend import add_executor_subparser
    add_executor_subparser(subparsers)

    # gateway command (P2-3)
    from gateway import add_gateway_subparser
    add_gateway_subparser(subparsers)

    # fork command (P2-4)
    from agent_fork import add_fork_subparser
    add_fork_subparser(subparsers)

    # perm command (P0-4)
    perm_parser = subparsers.add_parser("perm", help="权限管理（P0-4）")
    perm_sub = perm_parser.add_subparsers(dest="perm_command")
    perm_sub.add_parser("status", help="显示权限状态")
    perm_sub.add_parser("rules", help="显示当前权限规则")
    perm_mode_parser = perm_sub.add_parser("mode", help="切换权限模式")
    perm_mode_parser.add_argument("mode", type=str,
                                  choices=["default", "plan", "auto", "bypass"],
                                  help="权限模式")

    args = parser.parse_args()

    if not args.command:
        parser.print_help()
        return

    # install-deps 不需要检查依赖
    if args.command == "install-deps":
        install_deps()
        return

    # validate 不需要检查依赖
    if args.command == "validate":
        cli = ADDSCli()
        ok = cli.validate()
        sys.exit(0 if ok else 1)

    # list-skins 不需要检查依赖
    if args.command == "list-skins":
        cli = ADDSCli()
        cli.list_skins(preview=args.preview)
        return

    # 其他命令需要检查依赖
    if not check_dependencies():
        sys.exit(1)

    cli = ADDSCli()

    if args.command == "start":
        perm_mode = getattr(args, 'perm', 'default') or 'default'
        use_tui = getattr(args, 'tui', False)
        cli.start(role=args.role, non_interactive=args.non_interactive,
                  debug=args.debug, skin_name=args.skin,
                  perm_mode=perm_mode, tui=use_tui)
    elif args.command == "list-roles":
        cli.list_roles()
    elif args.command == "init":
        cli.init()
    elif args.command == "status":
        cli.status()
    elif args.command == "session":
        cli.session_command(args)
    elif args.command == "perm":
        cli.perm_command(args)
    elif args.command == "mem":
        cli.mem_command(args)
    elif args.command == "skill":
        from skill_manager import handle_skill_command
        handle_skill_command(args, project_root=str(cli.project_root))
    elif args.command == "schedule":
        from scheduler import handle_schedule_command
        handle_schedule_command(args, project_root=str(cli.project_root))
    elif args.command == "executor":
        from executor_backend import handle_executor_command
        handle_executor_command(args, project_root=str(cli.project_root))
    elif args.command == "gateway":
        from gateway import handle_gateway_command
        handle_gateway_command(args, project_root=str(cli.project_root))
    elif args.command == "fork":
        from agent_fork import handle_fork_command
        handle_fork_command(args, project_root=str(cli.project_root))


if __name__ == "__main__":
    main()
