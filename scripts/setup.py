#!/usr/bin/env python3
"""
ADDS Setup — 工具安装与权限配置

一键完成 scripts/ 目录下所有工具的安装与配置：
  - 为所有 Python 脚本设置可执行权限
  - 安装 git pre-commit hook（adds_security_hook）
  - 可选：将 adds.py 软链到 /usr/local/bin/adds（快捷访问）
  - 检测运行环境（Python 版本、git 可用性）

用法：
    python3 scripts/setup.py              # 标准安装
    python3 scripts/setup.py --no-symlink # 跳过全局符号链接
    python3 scripts/setup.py --check      # 只检查状态，不做任何修改
    python3 scripts/setup.py --uninstall  # 撤销安装（移除 hook 和符号链接）
"""

import argparse
import os
import shutil
import subprocess
import sys
from pathlib import Path


# ─────────────────────────────────────────────────────────
# 常量
# ─────────────────────────────────────────────────────────

MIN_PYTHON = (3, 9)
SYMLINK_TARGET = Path("/usr/local/bin/adds")

# 需要赋予可执行权限的脚本（相对于项目根目录）
EXECUTABLE_SCRIPTS = [
    "scripts/adds.py",
    "scripts/adds_security_hook.py",
    "scripts/compress_context.py",
    "scripts/init-adds.py",
    "scripts/install_hooks.py",
    "scripts/log_session.py",
    "scripts/validate_feature_list.py",
    "scripts/setup.py",
]

# git hook 配置：hook 名 -> 调用的脚本（相对于项目根）
GIT_HOOKS = {
    "pre-commit": "scripts/adds_security_hook.py",
}

HOOK_MARKER = "ADDS Security Hook"


# ─────────────────────────────────────────────────────────
# 工具函数
# ─────────────────────────────────────────────────────────

def find_git_root() -> Path | None:
    """向上查找 .git 目录，返回项目根路径。"""
    current = Path(__file__).resolve().parent.parent
    while current != current.parent:
        if (current / ".git").is_dir():
            return current
        current = current.parent
    return None


def check_python_version() -> bool:
    """检查 Python 版本是否满足最低要求。"""
    if sys.version_info < MIN_PYTHON:
        print(
            f"  ❌  Python {MIN_PYTHON[0]}.{MIN_PYTHON[1]}+ 是必须的，"
            f"当前版本为 {sys.version_info.major}.{sys.version_info.minor}"
        )
        return False
    print(
        f"  ✅  Python {sys.version_info.major}.{sys.version_info.minor}.{sys.version_info.micro}"
    )
    return True


def check_git_available() -> bool:
    """检查 git 是否可用。"""
    if shutil.which("git") is None:
        print("  ❌  git 未找到，请先安装 git")
        return False
    try:
        result = subprocess.run(
            ["git", "--version"],
            capture_output=True, text=True, check=True
        )
        print(f"  ✅  {result.stdout.strip()}")
        return True
    except subprocess.CalledProcessError:
        print("  ❌  git 命令执行失败")
        return False


# ─────────────────────────────────────────────────────────
# 核心步骤
# ─────────────────────────────────────────────────────────

def step_chmod(project_root: Path, dry_run: bool) -> list[str]:
    """为所有工具脚本设置可执行权限（chmod +x）。"""
    print("\n📝 配置脚本可执行权限 (chmod +x)...")
    results = []
    for rel_path in EXECUTABLE_SCRIPTS:
        script = project_root / rel_path
        if not script.exists():
            results.append(f"  ⚠️   未找到，跳过: {rel_path}")
            continue
        current_mode = script.stat().st_mode
        if current_mode & 0o111:
            results.append(f"  ○    已有执行权限: {rel_path}")
        else:
            if not dry_run:
                script.chmod(current_mode | 0o755)
            tag = "[DRY RUN] " if dry_run else ""
            results.append(f"  ✅  {tag}已设置 +x: {rel_path}")
    for r in results:
        print(r)
    return results


def step_install_hooks(project_root: Path, dry_run: bool, force: bool) -> list[str]:
    """安装 git hooks。"""
    print("\n🔗 安装 git hooks...")
    hooks_dir = project_root / ".git" / "hooks"
    results = []

    if not hooks_dir.is_dir():
        msg = "  ❌  .git/hooks/ 目录不存在，跳过 hook 安装"
        print(msg)
        return [msg]

    for hook_name, script_rel in GIT_HOOKS.items():
        hook_path = hooks_dir / hook_name
        source_path = project_root / script_rel

        if not source_path.exists():
            msg = f"  ❌  源脚本不存在: {script_rel}"
            print(msg)
            results.append(msg)
            continue

        if hook_path.exists() and not force:
            content = hook_path.read_text(encoding="utf-8", errors="ignore")
            if HOOK_MARKER not in content:
                msg = (
                    f"  ⚠️   {hook_name}: 已存在自定义 hook，跳过\n"
                    f"       手动链接：python3 \"{script_rel}\""
                )
                print(msg)
                results.append(msg)
                continue

        # 写 wrapper shell 脚本
        wrapper = (
            "#!/bin/sh\n"
            f"# {HOOK_MARKER} — {hook_name}\n"
            "# Installed by scripts/setup.py\n"
            f'python3 "$(git rev-parse --show-toplevel)/{script_rel}"\n'
        )
        tag = "[DRY RUN] " if dry_run else ""
        if not dry_run:
            hook_path.write_text(wrapper, encoding="utf-8")
            hook_path.chmod(0o755)
        action = "已更新" if (hook_path.exists() and not dry_run) else "已安装"
        msg = f"  ✅  {tag}{action}: .git/hooks/{hook_name}"
        print(msg)
        results.append(msg)

    return results


def step_symlink(project_root: Path, dry_run: bool) -> str:
    """将 adds.py 软链到 /usr/local/bin/adds。"""
    print(f"\n🔗 创建全局快捷命令 ({SYMLINK_TARGET})...")
    adds_py = project_root / "scripts" / "adds.py"

    if not adds_py.exists():
        msg = "  ❌  scripts/adds.py 不存在，跳过符号链接"
        print(msg)
        return msg

    if SYMLINK_TARGET.exists() or SYMLINK_TARGET.is_symlink():
        if SYMLINK_TARGET.is_symlink() and SYMLINK_TARGET.resolve() == adds_py.resolve():
            msg = f"  ○    符号链接已存在且指向正确: {SYMLINK_TARGET}"
            print(msg)
            return msg
        else:
            msg = f"  ⚠️   {SYMLINK_TARGET} 已存在（非本项目），跳过\n       如需覆盖请手动执行：ln -sf \"{adds_py}\" {SYMLINK_TARGET}"
            print(msg)
            return msg

    if dry_run:
        msg = f"  ✅  [DRY RUN] 将创建: {SYMLINK_TARGET} → {adds_py}"
        print(msg)
        return msg

    try:
        SYMLINK_TARGET.symlink_to(adds_py)
        msg = f"  ✅  已创建: {SYMLINK_TARGET} → {adds_py}"
        print(msg)
        return msg
    except PermissionError:
        msg = (
            f"  ⚠️   权限不足，无法写入 {SYMLINK_TARGET}\n"
            f"       请使用 sudo 重新执行，或手动运行：\n"
            f"       sudo ln -sf \"{adds_py}\" {SYMLINK_TARGET}"
        )
        print(msg)
        return msg


def step_uninstall(project_root: Path) -> None:
    """撤销安装：移除 hook 和符号链接。"""
    print("\n🗑️  卸载 ADDS 工具配置...")

    # 移除 git hooks
    hooks_dir = project_root / ".git" / "hooks"
    for hook_name in GIT_HOOKS:
        hook_path = hooks_dir / hook_name
        if hook_path.exists():
            content = hook_path.read_text(encoding="utf-8", errors="ignore")
            if HOOK_MARKER in content:
                hook_path.unlink()
                print(f"  ✅  已移除: .git/hooks/{hook_name}")
            else:
                print(f"  ⚠️   跳过 {hook_name}（非 ADDS 安装的 hook）")
        else:
            print(f"  ○    未安装: .git/hooks/{hook_name}")

    # 移除符号链接
    if SYMLINK_TARGET.is_symlink():
        adds_py = project_root / "scripts" / "adds.py"
        if SYMLINK_TARGET.resolve() == adds_py.resolve():
            try:
                SYMLINK_TARGET.unlink()
                print(f"  ✅  已移除: {SYMLINK_TARGET}")
            except PermissionError:
                print(
                    f"  ⚠️   权限不足，请手动执行：sudo rm {SYMLINK_TARGET}"
                )
        else:
            print(f"  ⚠️   {SYMLINK_TARGET} 非本项目链接，跳过")
    else:
        print(f"  ○    符号链接不存在: {SYMLINK_TARGET}")


def step_check(project_root: Path) -> None:
    """只读模式：显示当前状态，不做任何修改。"""
    print("\n🔍 当前状态检查")
    print("─" * 48)

    # 脚本权限
    print("\n📝 脚本可执行权限:")
    for rel_path in EXECUTABLE_SCRIPTS:
        script = project_root / rel_path
        if not script.exists():
            print(f"  ⚠️   未找到: {rel_path}")
            continue
        mode = script.stat().st_mode
        has_x = bool(mode & 0o111)
        tag = "✅  +x" if has_x else "○    无执行权限"
        print(f"  {tag}   {rel_path}")

    # git hooks
    print("\n🔗 Git Hooks:")
    hooks_dir = project_root / ".git" / "hooks"
    for hook_name in GIT_HOOKS:
        hook_path = hooks_dir / hook_name
        if hook_path.exists():
            content = hook_path.read_text(encoding="utf-8", errors="ignore")
            if HOOK_MARKER in content:
                print(f"  ✅  已安装 (ADDS): .git/hooks/{hook_name}")
            else:
                print(f"  ⚠️   已安装 (非ADDS): .git/hooks/{hook_name}")
        else:
            print(f"  ○    未安装: .git/hooks/{hook_name}")

    # 符号链接
    print(f"\n🔗 全局命令 ({SYMLINK_TARGET}):")
    if SYMLINK_TARGET.is_symlink():
        adds_py = project_root / "scripts" / "adds.py"
        if SYMLINK_TARGET.resolve() == adds_py.resolve():
            print(f"  ✅  已安装 → {SYMLINK_TARGET.resolve()}")
        else:
            print(f"  ⚠️   存在但指向其他位置: {SYMLINK_TARGET.resolve()}")
    elif SYMLINK_TARGET.exists():
        print(f"  ⚠️   存在但不是符号链接")
    else:
        print(f"  ○    未安装")


# ─────────────────────────────────────────────────────────
# 主入口
# ─────────────────────────────────────────────────────────

def main() -> None:
    parser = argparse.ArgumentParser(
        description="ADDS Setup — 工具安装与权限配置",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=(
            "示例：\n"
            "  python3 scripts/setup.py             # 标准安装\n"
            "  python3 scripts/setup.py --no-symlink # 不创建全局命令\n"
            "  python3 scripts/setup.py --check      # 只查看状态\n"
            "  python3 scripts/setup.py --uninstall  # 卸载\n"
            "  python3 scripts/setup.py --dry-run    # 预览操作，不实际执行\n"
        ),
    )
    parser.add_argument("--no-symlink", action="store_true", help="跳过创建 /usr/local/bin/adds 符号链接")
    parser.add_argument("--check", action="store_true", help="只显示安装状态，不做修改")
    parser.add_argument("--dry-run", action="store_true", help="预览将执行的操作，不实际修改")
    parser.add_argument("--uninstall", action="store_true", help="卸载（移除 hook 和符号链接）")
    parser.add_argument("--force", action="store_true", help="强制覆盖已有 hook")
    args = parser.parse_args()

    # ── Header ──
    print()
    print("╔══════════════════════════════════════════╗")
    print("║   ADDS Setup — 工具安装与权限配置         ║")
    print("╚══════════════════════════════════════════╝")

    # ── 环境检查 ──
    print("\n🔎 环境检查")
    print("─" * 48)
    ok_python = check_python_version()
    ok_git = check_git_available()

    if not ok_python:
        sys.exit(1)

    project_root = find_git_root()
    if project_root is None:
        print("  ❌  未找到 git 仓库根目录，请在项目目录中执行此脚本")
        sys.exit(1)
    print(f"  ✅  项目根目录: {project_root}")

    # ── 只读模式 ──
    if args.check:
        step_check(project_root)
        print()
        return

    # ── 卸载模式 ──
    if args.uninstall:
        step_uninstall(project_root)
        print("\n✅  卸载完成\n")
        return

    # ── 正式安装 ──
    if args.dry_run:
        print("\n⚠️   DRY RUN 模式 — 不会实际修改任何文件\n")

    step_chmod(project_root, dry_run=args.dry_run)

    if ok_git:
        step_install_hooks(project_root, dry_run=args.dry_run, force=args.force)
    else:
        print("\n⚠️   跳过 git hook 安装（git 不可用）")

    if not args.no_symlink:
        step_symlink(project_root, dry_run=args.dry_run)
    else:
        print("\n⏭️   已跳过全局符号链接（--no-symlink）")

    # ── 完成 ──
    print()
    if args.dry_run:
        print("══ DRY RUN 结束，未做任何修改 ══")
    else:
        print("══ 安装完成 ══")
        print()
        print("🚀 现在可以使用：")
        print("   python3 scripts/adds.py status      — 查看项目进度")
        print("   python3 scripts/adds.py next         — 下一个待开发特性")
        print("   python3 scripts/adds.py route        — 推荐 agent 角色")
        if not args.no_symlink and SYMLINK_TARGET.exists():
            print(f"   adds status                          — 全局快捷方式")
        print()
        print("   git hooks 已激活，commit 前会自动扫描安全规则。")
    print()


if __name__ == "__main__":
    main()
