#!/usr/bin/env python3
"""
ADDS Installer - AI-Driven Development Specification
Cross-platform: Windows, Linux, macOS
"""

import argparse
import logging
import os
import shutil
import subprocess
import sys
from pathlib import Path
from typing import Optional


logger = logging.getLogger(__name__)

ADDS_VERSION = "3.0.0"
ADDS_REPO = "https://github.com/tmacychen/ai-driven-dev-spec.git"
TEMP_DIR = "adds-temp-install"


def get_project_type() -> str:
    """Detect project type from existing files."""
    if Path("package.json").exists():
        return "Node.js"
    elif Path("Cargo.toml").exists():
        return "Rust"
    elif Path("go.mod").exists():
        return "Go"
    elif Path("requirements.txt").exists() or Path("pyproject.toml").exists():
        return "Python"
    elif Path("pom.xml").exists() or Path("build.gradle").exists():
        return "Java"
    elif list(Path(".").glob("*.csproj")):
        return "C#"
    return "Unknown"


def scan_existing_files() -> list[tuple[str, str]]:
    """Scan for existing project files."""
    files_to_check = [
        (".ai", "AI state directory"),
        ("app_spec.md", "Project specification"),
        ("CORE_GUIDELINES.md", "Quick reference"),
    ]

    existing = []
    for file, desc in files_to_check:
        if Path(file).exists():
            existing.append((file, desc))
    return existing


def get_user_action() -> str:
    """Get user action for existing files."""
    logger.info("")
    logger.info("Please choose an action:")
    logger.info("   [A] Replace All    - Replace all existing files")
    logger.info("   [S] Skip All      - Keep all existing files")
    logger.info("   [R] Review Each   - Review each file individually")
    logger.info("   [Q] Quit          - Cancel installation")
    logger.info("")
    while True:
        action = input("Choose action (A/S/R/Q): ").strip().upper()
        if action in ["A", "S", "R", "Q"]:
            return action


def should_replace_file(file: str, desc: str, force: bool, global_action: Optional[str]) -> bool:
    """Determine if a file should be replaced."""
    if force:
        return True
    if not global_action:
        return True

    if global_action == "A":
        return True
    elif global_action == "S":
        return False
    elif global_action == "R":
        logger.info(f"\n   File: {file} ({desc})")
        while True:
            yn = input("   Replace? (y/n/a/q): ").strip().lower()
            if yn in ["y", "a"]:
                if yn == "a":
                    return "A"
                return True
            elif yn in ["n", "q"]:
                return False
    return True


def install_from_git(source_dir: Path) -> bool:
    """Clone ADDS repository."""
    logger.info("Cloning ADDS repository...")
    try:
        subprocess.run(
            ["git", "clone", "--depth", "1", ADDS_REPO, TEMP_DIR],
            capture_output=True,
            check=True
        )
        return True
    except subprocess.CalledProcessError:
        logger.error("Failed to clone repository")
        logger.error("   Please check your internet connection or use --from-local")
        return False


def copy_scaffold(source_dir: Path, force: bool, dry_run: bool, global_action: Optional[str]):
    """Copy scaffold files."""
    if dry_run:
        logger.info("[DRY RUN] Would copy scaffold files to .ai/")
        return

    logger.info("Copying scaffold files...")
    Path(".ai").mkdir(exist_ok=True)

    files_to_copy = [
        ("templates/scaffold/.ai/feature_list.md", ".ai/feature_list.md"),
        ("templates/scaffold/.ai/progress.md", ".ai/progress.md"),
        ("templates/scaffold/.ai/architecture.md", ".ai/architecture.md"),
    ]

    for src, dest in files_to_copy:
        src_path = source_dir / src
        if src_path.exists():
            if should_replace_file(dest, "feature tracking", force, global_action):
                shutil.copy2(src_path, dest)
                logger.info(f"   Copied: {dest}")
            else:
                logger.info(f"   Skipped: {dest}")

    if should_replace_file("CORE_GUIDELINES.md", "quick reference", force, global_action):
        src_path = source_dir / "templates/scaffold/CORE_GUIDELINES.md"
        if src_path.exists():
            shutil.copy2(src_path, "CORE_GUIDELINES.md")
            logger.info("Copied: CORE_GUIDELINES.md")
    else:
        logger.info("Skipped: CORE_GUIDELINES.md")


def copy_prompts(source_dir: Path, force: bool, dry_run: bool, no_prompts: bool, global_action: Optional[str]):
    """Copy prompt templates."""
    if no_prompts:
        return

    if dry_run:
        logger.info("[DRY RUN] Would copy prompt templates to .ai/prompts/")
        return

    logger.info("Copying prompt templates...")
    Path(".ai/prompts").mkdir(exist_ok=True)

    if should_replace_file(".ai/prompts/", "prompt templates", force, global_action):
        src = source_dir / "templates/prompts"
        if src.exists():
            for f in src.glob("*"):
                if f.is_file():
                    shutil.copy2(f, f".ai/prompts/{f.name}")
            logger.info("Prompt templates copied")
    else:
        logger.info("Skipped: prompt templates")


def copy_docs(source_dir: Path, force: bool, dry_run: bool, global_action: Optional[str]):
    """Copy documentation."""
    if dry_run:
        logger.info("[DRY RUN] Would copy documentation to .ai/docs/")
        return

    logger.info("Copying documentation...")
    Path(".ai/docs").mkdir(exist_ok=True)

    if should_replace_file(".ai/docs/", "documentation", force, global_action):
        src = source_dir / "docs"
        if src.exists():
            for f in src.glob("*.md"):
                shutil.copy2(f, f".ai/docs/{f.name}")
            logger.info("Documentation copied")
    else:
        logger.info("Skipped: documentation")


def copy_scripts(source_dir: Path, force: bool, dry_run: bool, global_action: Optional[str]):
    """Copy utility scripts (CLI tools, hooks, etc.)."""
    if dry_run:
        logger.info("[DRY RUN] Would copy scripts to scripts/")
        return

    logger.info("Copying scripts...")
    scripts_src = source_dir / "scripts"
    if not scripts_src.exists():
        logger.warning("  Source scripts/ directory not found, skipping")
        return

    scripts_dest = Path("scripts")
    if not should_replace_file("scripts/", "utility scripts", force, global_action):
        logger.info("Skipped: scripts/")
        return

    scripts_dest.mkdir(exist_ok=True)
    copied = 0
    for f in scripts_src.glob("*.py"):
        dest = scripts_dest / f.name
        if not dest.exists() or should_replace_file(f"scripts/{f.name}", "script", force, global_action):
            shutil.copy2(f, dest)
            copied += 1
    logger.info(f"Scripts copied ({copied} files)")


def copy_schemas(source_dir: Path, dry_run: bool):
    """Copy JSON schemas used by validators."""
    if dry_run:
        logger.info("[DRY RUN] Would copy schemas to schemas/")
        return

    schemas_src = source_dir / "schemas"
    if not schemas_src.exists():
        return

    schemas_dest = Path("schemas")
    schemas_dest.mkdir(exist_ok=True)
    copied = 0
    for f in schemas_src.glob("*.json"):
        dest = schemas_dest / f.name
        if not dest.exists():
            shutil.copy2(f, dest)
            copied += 1
    if copied:
        logger.info(f"Schemas copied ({copied} files)")


def create_app_spec_template(dry_run: bool):
    """Create app_spec.md template if it doesn't exist."""
    if dry_run:
        if not Path("app_spec.md").exists():
            logger.info("[DRY RUN] Would create app_spec.md template")
        else:
            logger.info("[DRY RUN] app_spec.md exists, would skip")
        return

    if not Path("app_spec.md").exists():
        logger.info("Creating app_spec.md template...")
        content = """# Application Specification

> **Status**: DRAFT
> 
> Fill out this specification before starting development.

## Vision
{One paragraph describing what this project is and why it exists.}

## Goals
1. **{Goal 1}** — {Brief description}
2. **{Goal 2}** — {Brief description}
3. **{Goal 3}** — {Brief description}

## Non-Goals (Out of Scope)
- {What this project explicitly will NOT do}
- {Features that are intentionally excluded}

## Constraints
- {Technical constraint 1}
- {Business constraint 1}
- {Timeline constraint 1}

## Success Criteria
- [ ] {Measurable outcome 1}
- [ ] {Measurable outcome 2}
- [ ] {Measurable outcome 3}

## Technical Requirements

| Requirement | Priority | Notes |
|-------------|----------|-------|
| {Requirement 1} | Must-have | {Details} |
| {Requirement 2} | Should-have | {Details} |

---

*Last updated: <!-- date -->*
"""
        Path("app_spec.md").write_text(content, encoding="utf-8")
        logger.info("app_spec.md template created")
    else:
        logger.info("app_spec.md already exists, skipping")


def create_gitignore(dry_run: bool):
    """Create or merge .gitignore with project-type-specific rules."""
    if dry_run:
        logger.info("[DRY RUN] Would create/update .gitignore")
        return

    project_type = get_project_type()

    # Common entries for all projects
    common = [
        "# OS files",
        ".DS_Store",
        "Thumbs.db",
        "Desktop.ini",
        "",
        "# IDE",
        ".vscode/",
        ".idea/",
        "*.swp",
        "*.swo",
        "*~",
        "",
        "# Environment",
        ".env",
        ".env.local",
        ".env.*.local",
        "",
        "# ADDS working files",
        ".ai/session_log.jsonl",
        ".ai/test_failure_log.json",
        ".ai/training_data/",
        "",
    ]

    # Project-type-specific entries
    type_rules = {
        "Node.js": [
            "# Node.js",
            "node_modules/",
            "dist/",
            "build/",
            "*.tsbuildinfo",
            "coverage/",
            ".npm/",
            ".yarn/",
            "pnpm-lock.yaml",
        ],
        "Python": [
            "# Python",
            "__pycache__/",
            "*.py[cod]",
            "*.egg-info/",
            ".eggs/",
            "dist/",
            "build/",
            "*.egg",
            ".venv/",
            "venv/",
            ".pytest_cache/",
            ".mypy_cache/",
            "*.coverage",
            "htmlcov/",
        ],
        "Rust": [
            "# Rust",
            "target/",
            "**/*.rs.bk",
            "Cargo.lock",
        ],
        "Go": [
            "# Go",
            "vendor/",
        ],
        "Java": [
            "# Java",
            "*.class",
            "*.jar",
            "*.war",
            "target/",
            ".gradle/",
        ],
        "C#": [
            "# C#",
            "bin/",
            "obj/",
            "*.user",
            "*.suo",
        ],
    }

    lines = common.copy()
    lines.append(f"# {project_type} specific")
    lines.extend(type_rules.get(project_type, []))

    content = "\n".join(lines) + "\n"

    if Path(".gitignore").exists():
        # Merge: only append ADDS-specific and project-type entries that are missing
        existing = Path(".gitignore").read_text(encoding="utf-8")
        existing_lines = set(existing.splitlines())
        new_lines = [l for l in content.splitlines() if l not in existing_lines and not l.startswith("#")]
        new_comments = [l for l in content.splitlines() if l.startswith("#") and l not in existing_lines]

        if new_lines or new_comments:
            logger.info("Updating .gitignore with missing entries...")
            merged = existing.rstrip("\n") + "\n\n" + "# Added by ADDS installer\n" + content
            Path(".gitignore").write_text(merged, encoding="utf-8")
            logger.info(".gitignore updated")
        else:
            logger.info(".gitignore already covers all ADDS entries")
    else:
        logger.info("Creating .gitignore...")
        Path(".gitignore").write_text(content, encoding="utf-8")
        logger.info(".gitignore created")


def cleanup():
    """Clean up temporary files."""
    if Path(TEMP_DIR).exists():
        logger.info("Cleaning up...")
        shutil.rmtree(TEMP_DIR)


def run_upgrade(source_dir: Path, dry_run: bool, force: bool):
    """Upgrade existing ADDS installation.

    Only updates ADDS-managed files (prompts, docs, CORE_GUIDELINES.md).
    Preserves user data (feature_list.md, progress.md, architecture.md, app_spec.md).
    """
    # Files managed by ADDS (safe to update)
    managed_files = {
        "CORE_GUIDELINES.md": "quick reference",
    }

    logger.info("")
    logger.info("Upgrade mode: updating ADDS-managed files only")
    logger.info("   Preserving user data: feature_list.md, progress.md, architecture.md, app_spec.md")
    logger.info("")

    # 1. Update CORE_GUIDELINES.md
    for filepath, desc in managed_files.items():
        src_path = source_dir / "templates/scaffold" / filepath
        if src_path.exists():
            if dry_run:
                logger.info(f"[DRY RUN] Would update: {filepath}")
            else:
                shutil.copy2(src_path, filepath)
                logger.info(f"   Updated: {filepath}")
        else:
            logger.warning(f"   Source not found: {filepath}")

    # 2. Update prompts (clear old, copy new)
    if dry_run:
        logger.info("[DRY RUN] Would update: .ai/prompts/")
    else:
        prompts_src = source_dir / "templates/prompts"
        if prompts_src.exists():
            prompts_dest = Path(".ai/prompts")
            if prompts_dest.exists():
                # Remove old prompt files that no longer exist in source
                old_files = {f.name for f in prompts_dest.glob("*.md")}
                new_files = {f.name for f in prompts_src.glob("*.md")}
                removed = old_files - new_files
                if removed:
                    for f in removed:
                        (prompts_dest / f).unlink()
                        logger.info(f"   Removed deprecated: .ai/prompts/{f}")
            prompts_dest.mkdir(exist_ok=True)
            for f in prompts_src.glob("*.md"):
                shutil.copy2(f, prompts_dest / f.name)
            logger.info("   Updated: .ai/prompts/ (5 agent prompts)")

    # 3. Update docs
    if dry_run:
        logger.info("[DRY RUN] Would update: .ai/docs/")
    else:
        docs_src = source_dir / "docs"
        docs_dest = Path(".ai/docs")
        if docs_src.exists():
            docs_dest.mkdir(exist_ok=True)
            for f in docs_src.glob("*.md"):
                shutil.copy2(f, docs_dest / f.name)
            logger.info("   Updated: .ai/docs/")

    # 4. Update scripts (compress_context.py)
    scripts_dest = Path(".ai/scripts")
    if not scripts_dest.exists():
        scripts_src = source_dir / "scripts"
        if scripts_src.exists() and not dry_run:
            scripts_dest.mkdir(parents=True, exist_ok=True)
            for f in scripts_src.glob("*.py"):
                shutil.copy2(f, scripts_dest / f.name)
            logger.info("   Copied scripts to: .ai/scripts/")

    logger.info("")
    logger.info("Upgrade complete!")
    logger.info("   Your project data (features, progress, architecture) has been preserved.")


def print_next_steps():
    """Print next steps."""
    logger.info("")
    logger.info("=" * 40)
    logger.info(f"  ADDS v{ADDS_VERSION} Installed!")
    logger.info("=" * 40)
    logger.info("")
    logger.info("Files created:")
    logger.info("   .ai/                    - State management directory")
    logger.info("   .ai/feature_list.md     - Feature tracking")
    logger.info("   .ai/progress.md         - Session history")
    logger.info("   .ai/architecture.md    - Architecture document")
    logger.info("   .ai/prompts/            - AI prompts")
    logger.info("   .ai/docs/               - Documentation")
    logger.info("   scripts/                 - CLI tools & hooks")
    logger.info("   CORE_GUIDELINES.md      - Quick reference")
    logger.info("   app_spec.md             - Your project spec (edit this!)")
    logger.info("   .gitignore              - Git ignore rules")
    logger.info("")
    logger.info("Next steps:")
    logger.info("")
    logger.info("   1. Edit app_spec.md with your project requirements")
    logger.info("")
    logger.info('   2. Tell your AI assistant:')
    logger.info('      "Please read the files in the .ai directory')
    logger.info('       and start working according to the development specifications."')
    logger.info("")
    logger.info('   3. For subsequent sessions:')
    logger.info('      "Please read the files in the .ai directory')
    logger.info('       and continue development."')
    logger.info("")
    logger.info("ADDS CLI (optional):")
    logger.info("   python3 scripts/adds.py status     - Show progress")
    logger.info("   python3 scripts/adds.py next        - Next feature to implement")
    logger.info("   python3 scripts/adds.py route       - Recommended agent role")
    logger.info("")
    logger.info("Security hooks (optional):")
    logger.info("   python3 scripts/install_hooks.py     - Install pre-commit hook")
    logger.info("")
    logger.info("   Shortcut - add to PATH:")
    logger.info("   ln -s $(pwd)/scripts/adds.py /usr/local/bin/adds")
    logger.info("")
    logger.info("Documentation:")
    logger.info("   .ai/docs/specification.md     - Full specification")


def main():
    parser = argparse.ArgumentParser(
        description="ADDS Installer - AI-Driven Development Specification"
    )
    parser.add_argument(
        "--from-local",
        type=str,
        help="Install from local directory instead of git"
    )
    parser.add_argument(
        "--force",
        action="store_true",
        help="Force overwrite existing files without prompting"
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Show what would be installed without making changes"
    )
    parser.add_argument(
        "--no-prompts",
        action="store_true",
        help="Skip copying prompt templates"
    )
    parser.add_argument(
        "--upgrade",
        action="store_true",
        help="Upgrade ADDS-managed files while preserving user data"
    )
    parser.add_argument(
        "-v", "--verbose",
        action="store_true",
        help="Enable debug output"
    )
    parser.add_argument(
        "-q", "--quiet",
        action="store_true",
        help="Suppress info output"
    )

    args = parser.parse_args()

    logging.basicConfig(
        level=logging.DEBUG if args.verbose else (logging.WARNING if args.quiet else logging.INFO),
        format="%(message)s",
        stream=sys.stdout,
        force=True,
    )

    logger.info("")
    logger.info("=" * 40)
    logger.info(f"  ADDS v{ADDS_VERSION} Installer")
    logger.info("  AI-Driven Development Specification")
    logger.info("=" * 40)
    logger.info("")

    project_type = get_project_type()
    existing = scan_existing_files()

    logger.info("Scanning existing project files...")
    logger.info("")
    logger.info(f"   Detected project type: {project_type}")
    logger.info("")

    if existing:
        logger.info(f"   Found {len(existing)} existing file(s):")
        for file, desc in existing:
            logger.info(f"   Found: {file} ({desc})")
        logger.info("")

        if not args.force:
            action = get_user_action()

            if action == "Q":
                logger.info("\nInstallation cancelled.")
                sys.exit(0)
            elif action == "A":
                logger.info("\n-> Replacing all existing files...")
            elif action == "S":
                logger.info("\n-> Keeping all existing files...")
            elif action == "R":
                logger.info("\n-> Reviewing each file...")

            global_action = action
        else:
            global_action = "A"
    else:
        logger.info("   This appears to be an empty directory")
        global_action = "A"

    if args.dry_run:
        logger.info("")
        logger.info("=" * 40)
        logger.info("  DRY RUN - No files were changed")
        logger.info("=" * 40)

    if args.from_local:
        source_dir = Path(args.from_local)
        if not source_dir.exists():
            logger.error(f"Local path does not exist: {args.from_local}")
            sys.exit(1)
        logger.info(f"Using local ADDS from: {args.from_local}")
    else:
        if install_from_git(Path(".")):
            source_dir = Path(TEMP_DIR)
        else:
            sys.exit(1)

    if args.upgrade:
        # Verify this is an existing ADDS project
        if not Path("CORE_GUIDELINES.md").exists():
            logger.error("No ADDS installation found. Use normal install mode (without --upgrade).")
            sys.exit(1)
        run_upgrade(source_dir, args.dry_run, args.force)
        cleanup()
        return

    copy_scaffold(source_dir, args.force, args.dry_run, global_action)
    copy_prompts(source_dir, args.force, args.dry_run, args.no_prompts, global_action)
    copy_docs(source_dir, args.force, args.dry_run, global_action)
    copy_scripts(source_dir, args.force, args.dry_run, global_action)
    copy_schemas(source_dir, args.dry_run)
    create_app_spec_template(args.dry_run)
    create_gitignore(args.dry_run)
    cleanup()
    print_next_steps()


if __name__ == "__main__":
    main()
