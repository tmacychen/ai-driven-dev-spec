#!/usr/bin/env python3
"""
ADDS Hook Installer

Installs or removes ADDS git hooks.

Usage:
    python3 scripts/install_hooks.py          # Install hooks
    python3 scripts/install_hooks.py --remove  # Remove hooks
    python3 scripts/install_hooks.py --status  # Show hook status
"""

import argparse
import os
import shutil
import sys
from pathlib import Path


HOOKS = {
    "pre-commit": "adds_security_hook.py",
}


def find_git_root() -> Path:
    """Find the .git directory."""
    current = Path.cwd()
    while current != current.parent:
        if (current / ".git").is_dir():
            return current
        current = current.parent
    return None


def main():
    parser = argparse.ArgumentParser(description="ADDS Hook Installer")
    parser.add_argument("--remove", action="store_true", help="Remove installed hooks")
    parser.add_argument("--status", action="store_true", help="Show hook status")
    args = parser.parse_args()

    git_root = find_git_root()
    if not git_root:
        print("❌  Not a git repository", file=sys.stderr)
        sys.exit(1)

    hooks_dir = git_root / ".git" / "hooks"
    scripts_dir = git_root / "scripts"

    if args.status:
        print("🔍 ADDS Hook Status")
        print("─" * 42)
        for hook_name, script_name in HOOKS.items():
            hook_path = hooks_dir / hook_name
            source_path = scripts_dir / script_name
            hook_exists = hook_path.exists()
            source_exists = source_path.exists()
            status = "✅  installed" if hook_exists else "○  not installed"
            print(f"  {hook_name:20s}  {status}")
            if not source_exists:
                print(f"  ⚠️   source not found: {source_path.relative_to(git_root)}")
        return

    if args.remove:
        for hook_name in HOOKS:
            hook_path = hooks_dir / hook_name
            if hook_path.exists():
                backup = hook_path.with_suffix(".bak")
                # Check if it's our hook
                content = hook_path.read_text(encoding="utf-8", errors="ignore")
                if "ADDS Security Hook" in content or "adds_security_hook" in content:
                    hook_path.unlink()
                    print(f"✅  Removed: .git/hooks/{hook_name}")
                else:
                    print(f"⚠️   Skipping {hook_name}: appears to be a custom hook (not ADDS)")
            else:
                print(f"○   {hook_name}: not installed")
        return

    # Install
    print("📦 Installing ADDS hooks...")
    print()
    installed = []
    skipped = []

    for hook_name, script_name in HOOKS.items():
        hook_path = hooks_dir / hook_name
        source_path = scripts_dir / script_name

        if not source_path.exists():
            print(f"❌  Source not found: {source_path.relative_to(git_root)}")
            continue

        if hook_path.exists():
            content = hook_path.read_text(encoding="utf-8", errors="ignore")
            if "ADDS Security Hook" in content or "adds_security_hook" in content:
                # Update
                shutil.copy2(source_path, hook_path)
                hook_path.chmod(0o755)
                print(f"🔄 Updated: .git/hooks/{hook_name}")
                installed.append(hook_name)
            else:
                # Custom hook exists — don't overwrite
                print(f"⚠️   Skipping {hook_name}: custom hook already exists")
                print(f"    To chain manually, add this to your hook:")
                print(f"    python3 \"{source_path.relative_to(git_root)}\"")
                skipped.append(hook_name)
        else:
            # Write wrapper that calls the Python script
            wrapper = f"""#!/bin/sh
# ADDS Security Hook — pre-commit
# Installed by install_hooks.py
python3 "$(git rev-parse --show-toplevel)/scripts/{script_name}"
"""
            hook_path.write_text(wrapper, encoding="utf-8")
            hook_path.chmod(0o755)
            print(f"✅  Installed: .git/hooks/{hook_name}")
            installed.append(hook_name)

    print()
    if installed:
        print(f"🎉 {len(installed)} hook(s) installed")
        print()
        print("The pre-commit hook will now scan staged files for:")
        print("  - sudo / su usage")  # adds-security: allow
        print("  - curl | bash / wget | sh")  # adds-security: allow
        print("  - Network backdoors (nc, netcat, telnet)")  # adds-security: allow
        print("  - Destructive commands (rm -rf /, mkfs, fdisk)")  # adds-security: allow
        print("  - Network config changes (iptables, route)")
        print()
        print("To bypass a specific line, add this comment:")
        print("  # adds-security: allow")
        print()
        print("To remove hooks:  python3 scripts/install_hooks.py --remove")

    if skipped:
        print(f"⚠️   {len(skipped)} hook(s) skipped (custom hooks exist)")


if __name__ == "__main__":
    main()
