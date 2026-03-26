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
import logging
import shutil
import sys
from pathlib import Path


logger = logging.getLogger(__name__)


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
    parser.add_argument("-v", "--verbose", action="store_true", help="Enable debug output")
    parser.add_argument("-q", "--quiet", action="store_true", help="Suppress info output")
    args = parser.parse_args()

    logging.basicConfig(
        level=logging.DEBUG if args.verbose else (logging.WARNING if args.quiet else logging.INFO),
        format="%(message)s",
        stream=sys.stdout,
        force=True,
    )

    git_root = find_git_root()
    if not git_root:
        logger.error("Not a git repository")
        sys.exit(1)

    hooks_dir = git_root / ".git" / "hooks"
    scripts_dir = git_root / "scripts"

    if args.status:
        logger.info("ADDS Hook Status")
        logger.info("─" * 42)
        for hook_name, script_name in HOOKS.items():
            hook_path = hooks_dir / hook_name
            source_path = scripts_dir / script_name
            hook_exists = hook_path.exists()
            source_exists = source_path.exists()
            status = "installed" if hook_exists else "not installed"
            logger.info(f"  {hook_name:20s}  {status}")
            if not source_exists:
                logger.warning(f"  source not found: {source_path.relative_to(git_root)}")
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
                    logger.info(f"Removed: .git/hooks/{hook_name}")
                else:
                    logger.warning(f"Skipping {hook_name}: appears to be a custom hook (not ADDS)")
            else:
                logger.info(f"{hook_name}: not installed")
        return

    # Install
    logger.info("Installing ADDS hooks...")
    logger.info("")
    installed = []
    skipped = []

    for hook_name, script_name in HOOKS.items():
        hook_path = hooks_dir / hook_name
        source_path = scripts_dir / script_name

        if not source_path.exists():
            logger.error(f"Source not found: {source_path.relative_to(git_root)}")
            continue

        if hook_path.exists():
            content = hook_path.read_text(encoding="utf-8", errors="ignore")
            if "ADDS Security Hook" in content or "adds_security_hook" in content:
                # Update
                shutil.copy2(source_path, hook_path)
                hook_path.chmod(0o755)
                logger.info(f"Updated: .git/hooks/{hook_name}")
                installed.append(hook_name)
            else:
                # Custom hook exists — don't overwrite
                logger.warning(f"Skipping {hook_name}: custom hook already exists")
                logger.warning(f"    To chain manually, add this to your hook:")
                logger.warning(f"    python3 \"{source_path.relative_to(git_root)}\"")
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
            logger.info(f"Installed: .git/hooks/{hook_name}")
            installed.append(hook_name)

    logger.info("")
    if installed:
        logger.info(f"{len(installed)} hook(s) installed")
        logger.info("")
        logger.info("The pre-commit hook will now scan staged files for:")
        logger.info("  - sudo / su usage")
        logger.info("  - curl | bash / wget | sh")
        logger.info("  - Network backdoors (nc, netcat, telnet)")
        logger.info("  - Destructive commands (rm -rf /, mkfs, fdisk)")
        logger.info("  - Network config changes (iptables, route)")
        logger.info("")
        logger.info("To bypass a specific line, add this comment:")
        logger.info("  # adds-security: allow")
        logger.info("")
        logger.info("To remove hooks:  python3 scripts/install_hooks.py --remove")

    if skipped:
        logger.warning(f"{len(skipped)} hook(s) skipped (custom hooks exist)")


if __name__ == "__main__":
    main()
