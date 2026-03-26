#!/usr/bin/env python3
"""
ADDS Setup — AI-Driven Development Specification installer

Usage:
    python3 setup.py                        # Install to /usr/local/bin (default)
    python3 setup.py --prefix ~/.local      # Install to ~/.local/bin (no sudo needed)
    sudo python3 setup.py                   # Use when root access is required
    python3 setup.py --check                # Show installation status, no changes made
    python3 setup.py --upgrade              # Upgrade: reinstall current version + clean up old commands
    python3 setup.py --uninstall            # Uninstall: remove all installed tool scripts
    python3 setup.py --dry-run              # Preview what would happen without making any changes
    python3 setup.py --force                # Force overwrite even if destination is already up to date

Notes:
  • Install: copies scripts to <prefix>/bin/ and sets executable permissions (chmod +x).
  • Command names are derived automatically from script filenames (e.g. adds.py → adds).
  • Uninstall: removes commands listed in INSTALL_SCRIPTS; if a file is not found in the
    default directory, prints the command name and instructions for manual removal.
  • Upgrade: removes commands in REMOVED_SCRIPTS first, then force-installs the current version.

Release maintenance:
  On each release, update only these two variables below:
    INSTALL_SCRIPTS   — scripts to install in this version
    REMOVED_SCRIPTS   — command names dropped since last version (for upgrade/uninstall cleanup)
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
# ★ Release manifest — update only this section on each release ★
# ═══════════════════════════════════════════════════════════════

ADDS_VERSION = "3.0.1"

# Scripts to install in this version (paths relative to project root).
# Installed command name = filename without extension, for example:
#   scripts/adds.py          → adds
#   scripts/init_adds.py     → init-adds
#   scripts/install_hooks.py → install_hooks
#
# Release maintenance:
#   New tool    → add to this list
#   Removed tool → remove from this list and add its command name to REMOVED_SCRIPTS below
INSTALL_SCRIPTS: list[str] = [
    "scripts/adds.py",
    "scripts/init_adds.py",
    "scripts/install_hooks.py",
]

# Command names dropped since the last release (no path, no extension).
# These will be cleaned up during --upgrade and --uninstall.
# Example: if adds-log was present in v3.0.0 and is now removed, add "adds-log" here.
REMOVED_SCRIPTS: list[str] = [
    # "adds-log",
]

# Default installation prefix
DEFAULT_PREFIX = "/usr/local"


# ═══════════════════════════════════════════════════════════════
# Internal: derive command name from script path
# ═══════════════════════════════════════════════════════════════

def _cmd_name(script_rel: str) -> str:
    """Return the installed command name for a script path (stem only)."""
    return Path(script_rel).stem


# Build a {command_name: source_rel_path} mapping for internal use
def _build_manifest() -> dict[str, str]:
    return {_cmd_name(s): s for s in INSTALL_SCRIPTS}


# ═══════════════════════════════════════════════════════════════
# Data structures
# ═══════════════════════════════════════════════════════════════

@dataclass
class InstallResult:
    """Result for a single script operation."""
    name: str           # command name
    src: Path           # source file
    dest: Path          # destination file
    action: str         # installed / upgraded / skipped / failed / removed
    message: str = ""

    @property
    def ok(self) -> bool:
        return self.action not in ("failed",)


@dataclass
class SetupReport:
    """Summary report for the current operation."""
    results: list[InstallResult] = field(default_factory=list)

    def add(self, r: InstallResult) -> None:
        self.results.append(r)

    @property
    def has_failures(self) -> bool:
        return any(r.action == "failed" for r in self.results)


# ═══════════════════════════════════════════════════════════════
# Environment check
# ═══════════════════════════════════════════════════════════════

MIN_PYTHON = (3, 9)


def check_environment(prefix: Path) -> bool:
    """Check runtime environment. Returns True if requirements are met."""
    print("\n🔎 Environment check")
    print("─" * 52)

    ok = True

    # Python version
    vi = sys.version_info
    if vi < MIN_PYTHON:
        print(f"  ❌  Python {MIN_PYTHON[0]}.{MIN_PYTHON[1]}+ required, found {vi.major}.{vi.minor}.{vi.micro}")
        ok = False
    else:
        print(f"  ✅  Python {vi.major}.{vi.minor}.{vi.micro}")

    # Install directory
    bin_dir = prefix / "bin"
    if bin_dir.exists():
        if os.access(bin_dir, os.W_OK):
            print(f"  ✅  Install directory is writable: {bin_dir}")
        else:
            print(f"  ⚠️   Install directory is not writable: {bin_dir}")
            print(f"       Run with sudo, or use --prefix to specify a writable directory.")
            ok = False
    else:
        print(f"  ⚠️   Install directory does not exist: {bin_dir} (will be created)")

    # Source script check
    project_root = _project_root()
    missing = []
    for script_rel in INSTALL_SCRIPTS:
        src = project_root / script_rel
        if not src.exists():
            missing.append(script_rel)
    if missing:
        print(f"  ⚠️   The following source scripts were not found (incomplete clone?):")
        for m in missing:
            print(f"       - {m}")

    return ok


# ═══════════════════════════════════════════════════════════════
# Core operations
# ═══════════════════════════════════════════════════════════════

def _project_root() -> Path:
    """Return the project root (directory containing this setup.py)."""
    return Path(__file__).resolve().parent


def _make_executable(path: Path) -> None:
    """Add executable permission bits to a file (equivalent to chmod +x)."""
    current = path.stat().st_mode
    path.chmod(current | stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH)


def install(prefix: Path, dry_run: bool, force: bool) -> SetupReport:
    """Copy all tool scripts to <prefix>/bin/ and set executable permissions."""
    report = SetupReport()
    bin_dir = prefix / "bin"
    project_root = _project_root()
    manifest = _build_manifest()

    print(f"\n📦 Installing ADDS v{ADDS_VERSION} tools → {bin_dir}")
    print("─" * 52)

    if not dry_run:
        bin_dir.mkdir(parents=True, exist_ok=True)

    for name, rel in manifest.items():
        src = project_root / rel
        dest = bin_dir / name

        if not src.exists():
            r = InstallResult(name, src, dest, "failed",
                              f"Source file not found: {src}")
            report.add(r)
            print(f"  ❌  [failed    ]  {name:20s}  Source file not found: {src}")
            continue

        # Skip if already up to date
        if dest.exists() and not force:
            if dest.read_bytes() == src.read_bytes():
                r = InstallResult(name, src, dest, "skipped",
                                  f"Already up to date: {dest}")
                report.add(r)
                print(f"  ○   [skipped   ]  {name:20s}  Already up to date: {dest}")
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
    """Upgrade: reinstall current version and clean up removed commands."""
    print(f"\n⬆️  Upgrading ADDS → v{ADDS_VERSION}")
    print("─" * 52)

    report = SetupReport()
    bin_dir = prefix / "bin"

    # 1. Clean up commands removed in this version
    if REMOVED_SCRIPTS:
        print(f"\n  🗑️  The following commands were removed in this version and will be cleaned up:")
        results = _confirm_and_remove(REMOVED_SCRIPTS, bin_dir, dry_run,
                                      context="upgrade cleanup")
        for r in results:
            report.add(r)
    else:
        print("  ○   No obsolete commands to clean up in this version.")

    # 2. Install/update scripts for this version (force=True to overwrite)
    install_report = install(prefix, dry_run, force=True)
    report.results.extend(install_report.results)

    return report


def uninstall(prefix: Path, dry_run: bool) -> SetupReport:
    """Uninstall all tool scripts installed by the current version."""
    report = SetupReport()
    bin_dir = prefix / "bin"
    manifest = _build_manifest()

    print(f"\n🗑️  Uninstalling ADDS v{ADDS_VERSION} tools")
    print("─" * 52)

    # Uninstall scope = current version commands + legacy removed commands
    all_names = list(manifest.keys()) + REMOVED_SCRIPTS

    results = _confirm_and_remove(all_names, bin_dir, dry_run, context="uninstall")
    for r in results:
        report.add(r)

    return report


def check_status(prefix: Path) -> None:
    """Read-only: display current installation status."""
    bin_dir = prefix / "bin"
    project_root = _project_root()
    manifest = _build_manifest()

    print(f"\n🔍 ADDS v{ADDS_VERSION} installation status")
    print(f"   Install directory: {bin_dir}")
    print("─" * 52)

    print("\n📋 Tool scripts (this version):")
    for name, rel in manifest.items():
        src = project_root / rel
        dest = bin_dir / name

        if dest.exists():
            if src.exists() and dest.read_bytes() == src.read_bytes():
                status = "✅  Installed (up to date)"
            elif src.exists():
                status = "🔄  Installed (update available)"
            else:
                status = "✅  Installed (source not local)"
        else:
            status = "○   Not installed"

        x_flag = ""
        if dest.exists():
            m = dest.stat().st_mode
            x_flag = " [+x]" if (m & 0o111) else " [no exec permission]"

        print(f"  {status:35s}  {name}{x_flag}")
        print(f"      Source:  {rel}  →  {name}")
        print(f"      Path:    {dest}")

    if REMOVED_SCRIPTS:
        print(f"\n🗑️  Commands removed in this version (clean up if present):")
        for name in REMOVED_SCRIPTS:
            dest = bin_dir / name
            exists = "⚠️   Present (will be prompted for removal on --upgrade)" if dest.exists() else "○   Already removed"
            print(f"  {exists}")
            print(f"      Command: {name}")
            print(f"      Path:    {dest}")

    # PATH check
    print(f"\n🔗 PATH check:")
    path_dirs = os.environ.get("PATH", "").split(":")
    if str(bin_dir) in path_dirs:
        print(f"  ✅  {bin_dir} is in PATH")
    else:
        print(f"  ⚠️   {bin_dir} is not in PATH")
        print(f"       Add the following to your shell config:")
        print(f"       export PATH=\"$PATH:{bin_dir}\"")


# ═══════════════════════════════════════════════════════════════
# Helper functions
# ═══════════════════════════════════════════════════════════════

def _confirm_and_remove(
    names: list[str],
    bin_dir: Path,
    dry_run: bool,
    context: str = "removal",
) -> list[InstallResult]:
    """
    Show the list of files to delete, ask for confirmation, then delete.

    - Files found in bin_dir: list full paths and require y/N confirmation.
    - Files not found in bin_dir: print command name and manual removal instructions.
    - In dry_run mode: skip confirmation and just preview.
    """
    results: list[InstallResult] = []
    src = Path()  # no source file for removal operations

    found: list[tuple[str, Path]] = []     # (command name, full path)
    not_found: list[str] = []              # command names only

    for name in names:
        dest = bin_dir / name
        if dest.exists():
            found.append((name, dest))
        else:
            not_found.append(name)

    # ── Files not in default directory ──
    if not_found:
        print()
        print(f"  ⚠️   The following commands were not found in the default install directory ({bin_dir}).")
        print(f"       Please locate and remove them manually:")
        for name in not_found:
            print(f"       • {name}")
        print()
        print(f"       To find:   which {not_found[0]}")
        print(f"       To remove: rm -f <full path>")
        for name in not_found:
            results.append(InstallResult(name, src, bin_dir / name, "not_found",
                                         f"Not found in default directory, manual removal needed: {name}"))

    # ── Files found: show full paths and ask for confirmation ──
    if not found:
        if not not_found:
            print(f"\n  ○   Nothing to remove for {context} (none installed).")
        return results

    print()
    print(f"  The following files will be deleted ({context}):")
    print()
    for _, dest in found:
        print(f"      {dest}")
    print()

    if dry_run:
        print(f"  [DRY RUN] Preview only — no files will be deleted.")
        for name, dest in found:
            results.append(InstallResult(name, src, dest, "removed",
                                         f"[DRY RUN] Would delete: {dest}"))
        return results

    # Ask for confirmation
    try:
        answer = input(f"  Delete the {len(found)} file(s) listed above? [y/N] ").strip().lower()
    except (EOFError, KeyboardInterrupt):
        print()
        answer = "n"

    if answer not in ("y", "yes"):
        print(f"  {context.capitalize()} cancelled.")
        for name, dest in found:
            results.append(InstallResult(name, src, dest, "skipped", f"Cancelled by user: {dest}"))
        return results

    # Execute deletion
    print()
    failed_manual: list[Path] = []
    for name, dest in found:
        try:
            dest.unlink()
            print(f"  🗑️   Removed: {dest}")
            results.append(InstallResult(name, src, dest, "removed", f"Removed: {dest}"))
        except PermissionError:
            print(f"  ❌  Permission denied: {dest}")
            results.append(InstallResult(name, src, dest, "failed",
                                         f"Permission denied: {dest}"))
            failed_manual.append(dest)
        except OSError as e:
            print(f"  ❌  Failed to remove: {dest} ({e})")
            results.append(InstallResult(name, src, dest, "failed",
                                         f"Failed to remove: {dest} ({e})"))
            failed_manual.append(dest)

    if failed_manual:
        print()
        print("  ⚠️  The following files could not be removed. Please delete them manually:")
        for p in failed_manual:
            print(f"       rm -f \"{p}\"")
        print("  Or with elevated privileges:")
        for p in failed_manual:
            print(f"       sudo rm -f \"{p}\"")

    return results


def _make_executable(path: Path) -> None:
    """Add executable permission bits to a file (equivalent to chmod +x)."""
    current = path.stat().st_mode
    path.chmod(current | stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH)


def _print_post_install(prefix: Path, report: SetupReport) -> None:
    """Print usage instructions after a successful install."""
    bin_dir = prefix / "bin"
    installed = [r for r in report.results if r.action in ("installed", "upgraded")]
    if not installed:
        return

    path_dirs = os.environ.get("PATH", "").split(":")
    in_path = str(bin_dir) in path_dirs

    print()
    print("═" * 52)
    print(f"  ✅  ADDS v{ADDS_VERSION} installed successfully")
    print("═" * 52)
    print()

    print("📋 Installed commands:")
    for r in installed:
        print(f"   {r.dest}")
    print()

    print("🚀 Quick start:")
    print()
    print("   adds status          Overall project progress")
    print("   adds next            Next feature to implement")
    print("   adds route           Recommended agent role")
    print("   adds validate        Validate feature_list.md format")
    print("   adds dag             Visualize dependency graph")
    print("   adds compress        Compress progress.md context")
    print()

    if not in_path:
        shell_config = _detect_shell_config()
        print(f"⚠️   {bin_dir} is not in PATH. Run:")
        print()
        print(f'   echo \'export PATH="$PATH:{bin_dir}"\' >> {shell_config}')
        print(f"   source {shell_config}")
        print()

    print("📚 Docs: docs/specification.md")
    print()


def _detect_shell_config() -> str:
    """Guess the user's shell configuration file path."""
    shell = os.environ.get("SHELL", "")
    home = Path.home()
    if "zsh" in shell:
        return str(home / ".zshrc")
    if "fish" in shell:
        return str(home / ".config/fish/config.fish")
    if "bash" in shell:
        if sys.platform == "darwin":
            return str(home / ".bash_profile")
        return str(home / ".bashrc")
    return str(home / ".profile")


# ═══════════════════════════════════════════════════════════════
# 主入口
# ═══════════════════════════════════════════════════════════════

def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=f"ADDS v{ADDS_VERSION} Setup — Install / Upgrade / Uninstall",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=(
            "Examples:\n"
            "  python3 setup.py                        # Install to /usr/local/bin\n"
            "  python3 setup.py --prefix ~/.local      # Install to ~/.local/bin\n"
            "  sudo python3 setup.py                   # Install with root privileges\n"
            "  python3 setup.py --check                # Show installation status\n"
            "  python3 setup.py --upgrade              # Upgrade to this version\n"
            "  python3 setup.py --uninstall            # Uninstall all tools\n"
            "  python3 setup.py --dry-run              # Preview, no changes made\n"
        ),
    )
    parser.add_argument(
        "--prefix", default=DEFAULT_PREFIX, metavar="DIR",
        help=f"Installation prefix; tools are placed in <prefix>/bin/ (default: {DEFAULT_PREFIX})",
    )
    parser.add_argument("--check",     action="store_true", help="Show installation status without making any changes")
    parser.add_argument("--upgrade",   action="store_true", help="Upgrade to current version (removes obsolete commands first)")
    parser.add_argument("--uninstall", action="store_true", help="Remove all installed tool scripts")
    parser.add_argument("--dry-run",   action="store_true", help="Preview operations without modifying any files")
    parser.add_argument("--force",     action="store_true", help="Force overwrite even if destination is already up to date")
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
    print(f"   Install directory: {prefix / 'bin'}")

    if args.dry_run:
        print()
        print("   ⚠️  DRY RUN mode — no files will be modified")

    # ── Read-only mode ──
    if args.check:
        check_status(prefix)
        print()
        return

    # ── Uninstall (no environment check needed — deletion handles its own permission errors) ──
    if args.uninstall:
        report = uninstall(prefix, dry_run=args.dry_run)
        print()

        removed = [r for r in report.results if r.action == "removed"]
        failed = [r for r in report.results if r.action == "failed"]
        not_found = [r for r in report.results if r.action == "not_found"]
        skipped = [r for r in report.results if r.action == "skipped"]

        # User cancelled the prompt and no files were removed
        if not removed and skipped and not not_found:
            print("❌  Uninstall cancelled by user. No files were removed.")
            print()
            return

        # Nothing to remove (no installed files)
        if not removed and not_found and not skipped:
            print("○   Nothing to remove (none installed).")
            print()
            return

        if failed:
            print("⚠️  Some files could not be removed. See instructions above.")
            sys.exit(1)
        else:
            print(f"✅  Uninstall complete. Removed {len(removed)} file(s).")
            if not_found:
                print(f"  Note: {len(not_found)} command(s) were not found in {prefix / 'bin'}; manual removal may be needed.")
        print()
        return

    # ── Environment check (install / upgrade only) ──
    env_ok = check_environment(prefix)
    if not env_ok and not args.dry_run:
        print()
        print("❌  Environment check failed. Installation aborted.")
        print("    Fix the issues above or use --prefix to specify a writable directory.")
        print()
        sys.exit(1)

    # ── Upgrade ──
    if args.upgrade:
        report = upgrade(prefix, dry_run=args.dry_run)
        if not args.dry_run:
            _print_post_install(prefix, report)
        else:
            print("\n══ DRY RUN complete — no changes were made ══\n")
        if report.has_failures:
            sys.exit(1)
        return

    # ── Install ──
    report = install(prefix, dry_run=args.dry_run, force=args.force)
    if not args.dry_run:
        _print_post_install(prefix, report)
    else:
        print("\n══ DRY RUN complete — no changes were made ══\n")
    if report.has_failures:
        sys.exit(1)


if __name__ == "__main__":
    main()
