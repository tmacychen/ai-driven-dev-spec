#!/usr/bin/env python3
"""
ADDS Setup — AI-Driven Development Specification 安装程序

用法：
    python3 setup.py                        # 安装到默认目录 /usr/local/bin
    python3 setup.py --prefix ~/.local      # 安装到 ~/.local/bin（无需 sudo）
    sudo python3 setup.py                   # 需要 root 权限时使用
    python3 setup.py --check                # 只查看安装状态，不修改任何文件
    python3 setup.py --upgrade              # 升级：覆盖安装新版 + 清理旧命令
    python3 setup.py --uninstall            # 卸载：删除所有已安装的工具脚本
    python3 setup.py --dry-run              # 预览将执行的操作，不实际修改文件
    python3 setup.py --force                # 强制覆盖，即使目标文件内容相同

说明：
  • 安装：将工具脚本复制到 <prefix>/bin/，并自动设置可执行权限（chmod +x）。
  • 命令名由脚本文件名去掉扩展名自动生成（如 adds.py → adds）。
  • 卸载：依据 INSTALL_SCRIPTS 列表删除已安装的命令；若在默认路径找不到，
         会提示命令名和查找方法，由用户自行手动删除。
  • 升级：先清理 REMOVED_SCRIPTS 中的旧命令，再强制覆盖安装当前版本。

发版维护：
  每次发布新版本时，只需修改下方两处：
    INSTALL_SCRIPTS    — 本版本需要安装的脚本列表
    REMOVED_SCRIPTS    — 本版本废弃的旧命令名列表（供升级/卸载时清理）
"""

from __future__ import annotations

import argparse
import os
import shutil
import stat
import sys
from dataclasses import dataclass, field
from pathlib import Path


# ═══════════════════════════════════════════════════════════════
# ★ 发布清单 — 每次发版时只需维护这里 ★
# ═══════════════════════════════════════════════════════════════

ADDS_VERSION = "3.0.1"

# 本版本需要安装的脚本文件列表（相对于项目根目录）。
# 安装后的命令名 = 文件名去掉扩展名，例如：
#   scripts/adds.py          → adds
#   scripts/init-adds.py     → init-adds
#   scripts/install_hooks.py → install_hooks
#
# 发版维护规则：
#   新增工具 → 加入此列表
#   删除工具 → 从此列表移除，并加入下方 REMOVED_SCRIPTS
INSTALL_SCRIPTS: list[str] = [
    "scripts/adds.py",
    "scripts/init-adds.py",
    "scripts/install_hooks.py",
]

# 本版本需要删除的旧命令名（上一版本安装过、本版本不再提供）。
# 填写命令名（不含路径，不含扩展名），升级/卸载时会据此清理。
# 示例：上个版本有 adds-log，本版删除则写 "adds-log"
REMOVED_SCRIPTS: list[str] = [
    # "adds-log",
]

# 默认安装目录前缀
DEFAULT_PREFIX = "/usr/local"


# ═══════════════════════════════════════════════════════════════
# 内部：从脚本路径派生命令名
# ═══════════════════════════════════════════════════════════════

def _cmd_name(script_rel: str) -> str:
    """从脚本相对路径获取安装后的命令名（去掉目录和扩展名）。"""
    return Path(script_rel).stem


# 派生一个 {命令名: 源文件相对路径} 的映射，供内部使用
def _build_manifest() -> dict[str, str]:
    return {_cmd_name(s): s for s in INSTALL_SCRIPTS}


# ═══════════════════════════════════════════════════════════════
# 数据结构
# ═══════════════════════════════════════════════════════════════

@dataclass
class InstallResult:
    """单个脚本的安装结果。"""
    name: str           # 命令名
    src: Path           # 源文件
    dest: Path          # 目标文件
    action: str         # installed / upgraded / skipped / failed / removed
    message: str = ""

    @property
    def ok(self) -> bool:
        return self.action not in ("failed",)


@dataclass
class SetupReport:
    """本次操作的汇总报告。"""
    results: list[InstallResult] = field(default_factory=list)

    def add(self, r: InstallResult) -> None:
        self.results.append(r)

    @property
    def has_failures(self) -> bool:
        return any(r.action == "failed" for r in self.results)


# ═══════════════════════════════════════════════════════════════
# 环境检查
# ═══════════════════════════════════════════════════════════════

MIN_PYTHON = (3, 8)


def check_environment(prefix: Path) -> bool:
    """检查运行环境，返回是否满足安装要求。"""
    print("\n🔎 环境检查")
    print("─" * 52)

    ok = True

    # Python 版本
    vi = sys.version_info
    if vi < MIN_PYTHON:
        print(f"  ❌  Python {MIN_PYTHON[0]}.{MIN_PYTHON[1]}+ 是必须的，当前 {vi.major}.{vi.minor}.{vi.micro}")
        ok = False
    else:
        print(f"  ✅  Python {vi.major}.{vi.minor}.{vi.micro}")

    # 安装目录
    bin_dir = prefix / "bin"
    if bin_dir.exists():
        if os.access(bin_dir, os.W_OK):
            print(f"  ✅  安装目录可写: {bin_dir}")
        else:
            print(f"  ⚠️   安装目录不可写: {bin_dir}")
            print(f"       请用 sudo 运行，或用 --prefix 指定其他目录")
            ok = False
    else:
        print(f"  ⚠️   安装目录不存在: {bin_dir}（将尝试创建）")

    # 源脚本检查
    project_root = _project_root()
    missing = []
    for script_rel in INSTALL_SCRIPTS:
        src = project_root / script_rel
        if not src.exists():
            missing.append(script_rel)
    if missing:
        print(f"  ⚠️   以下源脚本未找到（可能是残缺的仓库克隆）:")
        for m in missing:
            print(f"       - {m}")

    return ok


# ═══════════════════════════════════════════════════════════════
# 核心操作
# ═══════════════════════════════════════════════════════════════

def _project_root() -> Path:
    """返回项目根目录（setup.py 所在目录）。"""
    return Path(__file__).resolve().parent


def _make_executable(path: Path) -> None:
    """给文件加上可执行权限（等效 chmod +x）。"""
    current = path.stat().st_mode
    path.chmod(current | stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH)


def install(prefix: Path, dry_run: bool, force: bool) -> SetupReport:
    """安装所有工具脚本到 <prefix>/bin/。"""
    report = SetupReport()
    bin_dir = prefix / "bin"
    project_root = _project_root()
    manifest = _build_manifest()

    print(f"\n📦 安装 ADDS v{ADDS_VERSION} 工具脚本 → {bin_dir}")
    print("─" * 52)

    if not dry_run:
        bin_dir.mkdir(parents=True, exist_ok=True)

    for name, rel in manifest.items():
        src = project_root / rel
        dest = bin_dir / name

        if not src.exists():
            r = InstallResult(name, src, dest, "failed",
                              f"源文件未找到: {src}")
            report.add(r)
            print(f"  ❌  [failed    ]  {name:20s}  源文件未找到: {src}")
            continue

        # 判断是否需要更新
        if dest.exists() and not force:
            if dest.read_bytes() == src.read_bytes():
                r = InstallResult(name, src, dest, "skipped",
                                  f"已是最新: {dest}")
                report.add(r)
                print(f"  ○   [skipped   ]  {name:20s}  已是最新: {dest}")
                continue

        action = "upgraded" if dest.exists() else "installed"
        tag = "[DRY RUN] " if dry_run else ""

        if not dry_run:
            shutil.copy2(src, dest)
            _make_executable(dest)

        r = InstallResult(name, src, dest, action, f"{tag}{dest}")
        report.add(r)
        print(f"  {'🔄' if action == 'upgraded' else '✅'}  [{action:10s}]  {name:20s}  {tag}{dest}")

    return report


def upgrade(prefix: Path, dry_run: bool) -> SetupReport:
    """升级：安装新版脚本，同时清理本版本移除的旧命令。"""
    print(f"\n⬆️  升级 ADDS → v{ADDS_VERSION}")
    print("─" * 52)

    report = SetupReport()
    bin_dir = prefix / "bin"

    # 1. 清理本版本移除的旧命令
    if REMOVED_SCRIPTS:
        print(f"\n  🗑️  以下旧命令在本版本中已移除，需要清理：")
        results = _confirm_and_remove(REMOVED_SCRIPTS, bin_dir, dry_run,
                                      context="升级清理")
        for r in results:
            report.add(r)
    else:
        print("  ○   本版本无需清理旧命令")

    # 2. 安装/更新新版脚本（force=True 确保覆盖旧内容）
    install_report = install(prefix, dry_run, force=True)
    report.results.extend(install_report.results)

    return report


def uninstall(prefix: Path, dry_run: bool) -> SetupReport:
    """卸载当前版本安装的所有工具脚本。"""
    report = SetupReport()
    bin_dir = prefix / "bin"
    manifest = _build_manifest()

    print(f"\n🗑️  卸载 ADDS v{ADDS_VERSION} 工具脚本")
    print("─" * 52)

    # 卸载清单 = 当前版本的命令 + 历史遗留的旧命令
    all_names = list(manifest.keys()) + REMOVED_SCRIPTS

    results = _confirm_and_remove(all_names, bin_dir, dry_run, context="卸载")
    for r in results:
        report.add(r)

    return report


def check_status(prefix: Path) -> None:
    """只读：显示当前安装状态。"""
    bin_dir = prefix / "bin"
    project_root = _project_root()
    manifest = _build_manifest()

    print(f"\n🔍 ADDS v{ADDS_VERSION} 安装状态检查")
    print(f"   安装目录: {bin_dir}")
    print("─" * 52)

    print("\n📋 工具脚本（本版本清单）：")
    for name, rel in manifest.items():
        src = project_root / rel
        dest = bin_dir / name

        if dest.exists():
            if src.exists() and dest.read_bytes() == src.read_bytes():
                status = "✅  已安装（最新）"
            elif src.exists():
                status = "🔄  已安装（有新版本可升级）"
            else:
                status = "✅  已安装（源文件不在本地）"
        else:
            status = "○   未安装"

        x_flag = ""
        if dest.exists():
            m = dest.stat().st_mode
            x_flag = " [+x]" if (m & 0o111) else " [无执行权限]"

        print(f"  {status:30s}  {name}{x_flag}")
        print(f"      命令名来源: {rel}  →  {name}")
        print(f"      安装路径:   {dest}")

    if REMOVED_SCRIPTS:
        print(f"\n🗑️  本版本已移除的旧命令（如存在则需清理）：")
        for name in REMOVED_SCRIPTS:
            dest = bin_dir / name
            exists = "⚠️   存在（升级时将自动提示删除）" if dest.exists() else "○   已清理"
            print(f"  {exists}")
            print(f"      命令: {name}")
            print(f"      路径: {dest}")

    # PATH 检查
    print(f"\n🔗 PATH 检查：")
    path_dirs = os.environ.get("PATH", "").split(":")
    if str(bin_dir) in path_dirs:
        print(f"  ✅  {bin_dir} 已在 PATH 中")
    else:
        print(f"  ⚠️   {bin_dir} 不在 PATH 中")
        print(f"       请将以下内容加入 shell 配置文件：")
        print(f"       export PATH=\"$PATH:{bin_dir}\"")


# ═══════════════════════════════════════════════════════════════
# 工具函数
# ═══════════════════════════════════════════════════════════════

def _confirm_and_remove(
    names: list[str],
    bin_dir: Path,
    dry_run: bool,
    context: str = "删除",
) -> list[InstallResult]:
    """
    展示待删除文件列表，请用户确认后再执行删除。

    - 默认路径（bin_dir）存在的文件：列出完整路径，请用户确认。
    - 默认路径找不到的文件：提示命令名，请用户自行查找删除。
    - dry_run 时跳过确认，直接展示预览。
    """
    results: list[InstallResult] = []
    src = Path()  # 删除操作无源文件

    found: list[tuple[str, Path]] = []     # (命令名, 完整路径)
    not_found: list[str] = []              # 命令名

    for name in names:
        dest = bin_dir / name
        if dest.exists():
            found.append((name, dest))
        else:
            not_found.append(name)

    # ── 默认路径找不到的 ──
    if not_found:
        print()
        print(f"  ⚠️   以下命令在默认安装目录 ({bin_dir}) 中未找到，")
        print(f"       请自行在系统 PATH 中查找并手动删除：")
        for name in not_found:
            print(f"       • {name}")
        print()
        print(f"       查找方法：  which {not_found[0]}")
        print(f"       删除方法：  rm -f <完整路径>")
        for name in not_found:
            results.append(InstallResult(name, src, bin_dir / name, "skipped",
                                         f"默认路径未找到，请手动查找: {name}"))

    # ── 找到的文件：展示完整路径，请用户确认 ──
    if not found:
        if not not_found:
            print(f"\n  ○   无需{context}任何文件（均未安装）")
        return results

    print()
    print(f"  以下文件将被删除（{context}）：")
    print()
    for _, dest in found:
        print(f"      {dest}")
    print()

    if dry_run:
        print(f"  [DRY RUN] 预览模式，不实际执行删除")
        for name, dest in found:
            results.append(InstallResult(name, src, dest, "removed",
                                         f"[DRY RUN] 将删除: {dest}"))
        return results

    # 请用户确认
    try:
        answer = input(f"  确认删除以上 {len(found)} 个文件？[y/N] ").strip().lower()
    except (EOFError, KeyboardInterrupt):
        print()
        answer = "n"

    if answer not in ("y", "yes"):
        print(f"  已取消{context}。")
        for name, dest in found:
            results.append(InstallResult(name, src, dest, "skipped", f"用户取消: {dest}"))
        return results

    # 执行删除
    print()
    failed_manual: list[Path] = []
    for name, dest in found:
        try:
            dest.unlink()
            print(f"  🗑️   已删除: {dest}")
            results.append(InstallResult(name, src, dest, "removed", f"已删除: {dest}"))
        except PermissionError:
            print(f"  ❌  权限不足: {dest}")
            results.append(InstallResult(name, src, dest, "failed",
                                         f"权限不足，无法删除: {dest}"))
            failed_manual.append(dest)
        except OSError as e:
            print(f"  ❌  删除失败: {dest} ({e})")
            results.append(InstallResult(name, src, dest, "failed",
                                         f"删除失败: {dest} ({e})"))
            failed_manual.append(dest)

    if failed_manual:
        print()
        print("  ⚠️  以下文件删除失败，请手动执行：")
        for p in failed_manual:
            print(f"       rm -f \"{p}\"")
        print("  或以管理员权限运行：")
        for p in failed_manual:
            print(f"       sudo rm -f \"{p}\"")

    return results


def _make_executable(path: Path) -> None:
    """给文件加上可执行权限（等效 chmod +x）。"""
    current = path.stat().st_mode
    path.chmod(current | stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH)


def _print_post_install(prefix: Path, report: SetupReport) -> None:
    """安装完成后打印使用说明。"""
    bin_dir = prefix / "bin"
    installed = [r for r in report.results if r.action in ("installed", "upgraded")]
    if not installed:
        return

    path_dirs = os.environ.get("PATH", "").split(":")
    in_path = str(bin_dir) in path_dirs

    print()
    print("═" * 52)
    print(f"  ✅  ADDS v{ADDS_VERSION} 安装完成")
    print("═" * 52)
    print()

    # 列出已安装的命令
    print("📋 已安装命令：")
    for r in installed:
        print(f"   {r.dest}")
    print()

    print("🚀 快速开始：")
    print()
    print("   adds status          查看项目进度")
    print("   adds next            下一个待开发特性")
    print("   adds route           推荐 agent 角色")
    print("   adds validate        检验 feature_list.md 格式")
    print("   adds dag             可视化依赖图")
    print("   adds compress        压缩 progress.md 上下文")
    print()

    if not in_path:
        shell_config = _detect_shell_config()
        print(f"⚠️   {bin_dir} 尚未加入 PATH，请运行：")
        print()
        print(f'   echo \'export PATH="$PATH:{bin_dir}"\' >> {shell_config}')
        print(f"   source {shell_config}")
        print()

    print("📚 文档：docs/specification.md")
    print()


def _detect_shell_config() -> str:
    """猜测用户的 shell 配置文件路径。"""
    shell = os.environ.get("SHELL", "")
    home = Path.home()
    if "zsh" in shell:
        return str(home / ".zshrc")
    if "fish" in shell:
        return str(home / ".config/fish/config.fish")
    if "bash" in shell:
        # macOS 默认用 .bash_profile，Linux 用 .bashrc
        if sys.platform == "darwin":
            return str(home / ".bash_profile")
        return str(home / ".bashrc")
    return str(home / ".profile")


# ═══════════════════════════════════════════════════════════════
# 主入口
# ═══════════════════════════════════════════════════════════════

def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=f"ADDS v{ADDS_VERSION} Setup — 安装 / 升级 / 卸载",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=(
            "示例：\n"
            "  python3 setup.py                        # 安装到 /usr/local/bin\n"
            "  python3 setup.py --prefix ~/.local      # 安装到 ~/.local/bin\n"
            "  sudo python3 setup.py                   # 需要 root 时\n"
            "  python3 setup.py --check                # 查看安装状态\n"
            "  python3 setup.py --upgrade              # 升级到最新版本\n"
            "  python3 setup.py --uninstall            # 卸载\n"
            "  python3 setup.py --dry-run              # 预览，不实际执行\n"
        ),
    )
    parser.add_argument(
        "--prefix", default=DEFAULT_PREFIX, metavar="DIR",
        help=f"安装目录前缀，工具会安装到 <prefix>/bin/（默认: {DEFAULT_PREFIX}）",
    )
    parser.add_argument("--check",     action="store_true", help="只显示安装状态，不做任何修改")
    parser.add_argument("--upgrade",   action="store_true", help="升级到当前版本（保留用户数据）")
    parser.add_argument("--uninstall", action="store_true", help="卸载所有已安装的工具脚本")
    parser.add_argument("--dry-run",   action="store_true", help="预览将执行的操作，不实际修改任何文件")
    parser.add_argument("--force",     action="store_true", help="强制覆盖，即使目标文件内容相同")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    prefix = Path(args.prefix).expanduser().resolve()

    # ── Header ──
    print()
    print("╔══════════════════════════════════════════════════╗")
    print(f"║   ADDS v{ADDS_VERSION} Setup                              ║")
    print("║   AI-Driven Development Specification            ║")
    print("╚══════════════════════════════════════════════════╝")
    print(f"   安装目录: {prefix / 'bin'}")

    if args.dry_run:
        print()
        print("   ⚠️  DRY RUN 模式 — 不会实际修改任何文件")

    # ── 只读模式 ──
    if args.check:
        check_status(prefix)
        print()
        return

    # ── 卸载（不需要写权限检查，删除操作自带权限错误提示）──
    if args.uninstall:
        report = uninstall(prefix, dry_run=args.dry_run)
        print()
        if report.has_failures:
            print("⚠️  部分卸载失败，请参考上方提示手动清理。")
            sys.exit(1)
        else:
            print("✅  卸载完成。")
        print()
        return

    # ── 升级 / 安装时做环境检查 ──
    env_ok = check_environment(prefix)
    if not env_ok and not args.dry_run:
        print()
        print("❌  环境检查未通过，安装中止。")
        print("    请修复上述问题后重试，或使用 --prefix 指定有写权限的目录。")
        print()
        sys.exit(1)

    # ── 升级 ──
    if args.upgrade:
        report = upgrade(prefix, dry_run=args.dry_run)
        if not args.dry_run:
            _print_post_install(prefix, report)
        else:
            print("\n══ DRY RUN 结束，未做任何修改 ══\n")
        if report.has_failures:
            sys.exit(1)
        return

    # ── 安装 ──
    report = install(prefix, dry_run=args.dry_run, force=args.force)
    if not args.dry_run:
        _print_post_install(prefix, report)
    else:
        print("\n══ DRY RUN 结束，未做任何修改 ══\n")
    if report.has_failures:
        sys.exit(1)


if __name__ == "__main__":
    main()
