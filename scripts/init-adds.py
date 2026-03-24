#!/usr/bin/env python3
"""
ADDS Installer - AI-Driven Development Specification
Cross-platform: Windows, Linux, macOS
"""

import os
import sys
import shutil
import argparse
import subprocess
from pathlib import Path
from typing import Optional

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
    print("\nPlease choose an action:")
    print("   [A] Replace All    - Replace all existing files")
    print("   [S] Skip All      - Keep all existing files")
    print("   [R] Review Each   - Review each file individually")
    print("   [Q] Quit          - Cancel installation")
    print()
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
        print(f"\n   File: {file} ({desc})")
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
    print("📥 Cloning ADDS repository...")
    try:
        subprocess.run(
            ["git", "clone", "--depth", "1", ADDS_REPO, TEMP_DIR],
            capture_output=True,
            check=True
        )
        return True
    except subprocess.CalledProcessError:
        print("❌ Failed to clone repository")
        print("   Please check your internet connection or use --from-local")
        return False


def copy_scaffold(source_dir: Path, force: bool, dry_run: bool, global_action: Optional[str]):
    """Copy scaffold files."""
    if dry_run:
        print("📋 [DRY RUN] Would copy scaffold files to .ai/")
        return
    
    print("📋 Copying scaffold files...")
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
                print(f"   ✅ Copied: {dest}")
            else:
                print(f"   ⏭️  Skipped: {dest}")
    
    if should_replace_file("CORE_GUIDELINES.md", "quick reference", force, global_action):
        src_path = source_dir / "templates/scaffold/CORE_GUIDELINES.md"
        if src_path.exists():
            shutil.copy2(src_path, "CORE_GUIDELINES.md")
            print("✅ Copied: CORE_GUIDELINES.md")
    else:
        print("⏭️  Skipped: CORE_GUIDELINES.md")


def copy_prompts(source_dir: Path, force: bool, dry_run: bool, no_prompts: bool, global_action: Optional[str]):
    """Copy prompt templates."""
    if no_prompts:
        return
    
    if dry_run:
        print("📋 [DRY RUN] Would copy prompt templates to .ai/prompts/")
        return
    
    print("📋 Copying prompt templates...")
    Path(".ai/prompts").mkdir(exist_ok=True)
    
    if should_replace_file(".ai/prompts/", "prompt templates", force, global_action):
        src = source_dir / "templates/prompts"
        if src.exists():
            for f in src.glob("*"):
                if f.is_file():
                    shutil.copy2(f, f".ai/prompts/{f.name}")
            print("✅ Prompt templates copied")
    else:
        print("⏭️  Skipped: prompt templates")


def copy_docs(source_dir: Path, force: bool, dry_run: bool, global_action: Optional[str]):
    """Copy documentation."""
    if dry_run:
        print("📋 [DRY RUN] Would copy documentation to .ai/docs/")
        return
    
    print("📋 Copying documentation...")
    Path(".ai/docs").mkdir(exist_ok=True)
    
    if should_replace_file(".ai/docs/", "documentation", force, global_action):
        src = source_dir / "docs"
        if src.exists():
            for f in src.glob("*.md"):
                shutil.copy2(f, f".ai/docs/{f.name}")
            print("✅ Documentation copied")
    else:
        print("⏭️  Skipped: documentation")


def create_app_spec_template(dry_run: bool):
    """Create app_spec.md template if it doesn't exist."""
    if dry_run:
        if not Path("app_spec.md").exists():
            print("📝 [DRY RUN] Would create app_spec.md template")
        else:
            print("📝 [DRY RUN] app_spec.md exists, would skip")
        return
    
    if not Path("app_spec.md").exists():
        print("📝 Creating app_spec.md template...")
        content = """# Application Specification

> **Status**: DRAFT
> 
> ⚠️ Fill out this specification before starting development.

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
        print("✅ app_spec.md template created")
    else:
        print("ℹ️  app_spec.md already exists, skipping")


def create_gitignore(dry_run: bool):
    """Create or merge .gitignore with project-type-specific rules."""
    if dry_run:
        print("📝 [DRY RUN] Would create/update .gitignore")
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
            print("📝 Updating .gitignore with missing entries...")
            merged = existing.rstrip("\n") + "\n\n" + "# Added by ADDS installer\n" + content
            Path(".gitignore").write_text(merged, encoding="utf-8")
            print("✅ .gitignore updated")
        else:
            print("ℹ️  .gitignore already covers all ADDS entries")
    else:
        print("📝 Creating .gitignore...")
        Path(".gitignore").write_text(content, encoding="utf-8")
        print("✅ .gitignore created")


def cleanup():
    """Clean up temporary files."""
    if Path(TEMP_DIR).exists():
        print("🧹 Cleaning up...")
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

    print()
    print("📦 Upgrade mode: updating ADDS-managed files only")
    print("   Preserving user data: feature_list.md, progress.md, architecture.md, app_spec.md")
    print()

    # 1. Update CORE_GUIDELINES.md
    for filepath, desc in managed_files.items():
        src_path = source_dir / "templates/scaffold" / filepath
        if src_path.exists():
            if dry_run:
                print(f"📋 [DRY RUN] Would update: {filepath}")
            else:
                shutil.copy2(src_path, filepath)
                print(f"   ✅ Updated: {filepath}")
        else:
            print(f"   ⚠️  Source not found: {filepath}")

    # 2. Update prompts (clear old, copy new)
    if dry_run:
        print("📋 [DRY RUN] Would update: .ai/prompts/")
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
                        print(f"   🗑️  Removed deprecated: .ai/prompts/{f}")
            prompts_dest.mkdir(exist_ok=True)
            for f in prompts_src.glob("*.md"):
                shutil.copy2(f, prompts_dest / f.name)
            print("   ✅ Updated: .ai/prompts/ (5 agent prompts)")

    # 3. Update docs
    if dry_run:
        print("📋 [DRY RUN] Would update: .ai/docs/")
    else:
        docs_src = source_dir / "docs"
        docs_dest = Path(".ai/docs")
        if docs_src.exists():
            docs_dest.mkdir(exist_ok=True)
            for f in docs_src.glob("*.md"):
                shutil.copy2(f, docs_dest / f.name)
            print("   ✅ Updated: .ai/docs/")

    # 4. Update scripts (compress_context.py)
    scripts_dest = Path(".ai/scripts")
    if not scripts_dest.exists():
        scripts_src = source_dir / "scripts"
        if scripts_src.exists() and not dry_run:
            scripts_dest.mkdir(parents=True, exist_ok=True)
            for f in scripts_src.glob("*.py"):
                shutil.copy2(f, scripts_dest / f.name)
            print("   ✅ Copied scripts to: .ai/scripts/")

    print()
    print("✅ Upgrade complete!")
    print("   Your project data (features, progress, architecture) has been preserved.")


def print_next_steps():
    """Print next steps."""
    print()
    print("========================================")
    print(f"  ✅ ADDS v{ADDS_VERSION} Installed!")
    print("========================================")
    print()
    print("📁 Files created:")
    print("   .ai/                    - State management directory")
    print("   .ai/feature_list.md     - Feature tracking")
    print("   .ai/progress.md         - Session history")
    print("   .ai/architecture.md    - Architecture document")
    print("   .ai/prompts/            - AI prompts")
    print("   .ai/docs/               - Documentation")
    print("   CORE_GUIDELINES.md      - Quick reference")
    print("   app_spec.md             - Your project spec (edit this!)")
    print("   .gitignore              - Git ignore rules")
    print()
    print("🚀 Next steps:")
    print()
    print("   1. Edit app_spec.md with your project requirements")
    print()
    print('   2. Tell your AI assistant:')
    print('      "Please read the files in the .ai directory')
    print('       and start working according to the development specifications."')
    print()
    print('   3. For subsequent sessions:')
    print('      "Please read the files in the .ai directory')
    print('       and continue development."')
    print()
    print("📚 Documentation:")
    print("   .ai/docs/specification.md     - Full specification")


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
    
    args = parser.parse_args()
    
    print()
    print("========================================")
    print(f"  ADDS v{ADDS_VERSION} Installer")
    print("  AI-Driven Development Specification")
    print("========================================")
    print()
    
    project_type = get_project_type()
    existing = scan_existing_files()
    
    print("📊 Scanning existing project files...")
    print()
    print(f"   Detected project type: {project_type}")
    print()
    
    if existing:
        print(f"   Found {len(existing)} existing file(s):")
        for file, desc in existing:
            print(f"   ⚠️  Found: {file} ({desc})")
        print()
        
        if not args.force:
            action = get_user_action()
            
            if action == "Q":
                print("\nInstallation cancelled.")
                sys.exit(0)
            elif action == "A":
                print("\n→ Replacing all existing files...")
            elif action == "S":
                print("\n→ Keeping all existing files...")
            elif action == "R":
                print("\n→ Reviewing each file...")
            
            global_action = action
        else:
            global_action = "A"
    else:
        print("   ✅ This appears to be an empty directory")
        global_action = "A"
    
    if args.dry_run:
        print()
        print("========================================")
        print("  ⚠️  DRY RUN - No files were changed")
        print("========================================")
    
    if args.from_local:
        source_dir = Path(args.from_local)
        if not source_dir.exists():
            print(f"❌ Local path does not exist: {args.from_local}")
            sys.exit(1)
        print(f"📁 Using local ADDS from: {args.from_local}")
    else:
        if install_from_git(Path(".")):
            source_dir = Path(TEMP_DIR)
        else:
            sys.exit(1)

    if args.upgrade:
        # Verify this is an existing ADDS project
        if not Path("CORE_GUIDELINES.md").exists():
            print("❌ No ADDS installation found. Use normal install mode (without --upgrade).")
            sys.exit(1)
        run_upgrade(source_dir, args.dry_run, args.force)
        cleanup()
        return

    copy_scaffold(source_dir, args.force, args.dry_run, global_action)
    copy_prompts(source_dir, args.force, args.dry_run, args.no_prompts, global_action)
    copy_docs(source_dir, args.force, args.dry_run, global_action)
    create_app_spec_template(args.dry_run)
    create_gitignore(args.dry_run)
    cleanup()
    print_next_steps()


if __name__ == "__main__":
    main()
