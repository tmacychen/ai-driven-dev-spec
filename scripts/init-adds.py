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

ADDS_VERSION = "2.3"
ADDS_REPO = "https://github.com/your-repo/ai-driven-dev-spec.git"
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


def cleanup():
    """Clean up temporary files."""
    if Path(TEMP_DIR).exists():
        print("🧹 Cleaning up...")
        shutil.rmtree(TEMP_DIR)


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
        "--help",
        action="store_true",
        help="Show this help message"
    )
    
    args = parser.parse_args()
    
    if args.help:
        parser.print_help()
        print("\nExamples:")
        print("  python init-adds.py                          # Install from git")
        print("  python init-adds.py --from-local ../adds    # Install from local")
        print("  python init-adds.py --force                 # Force overwrite")
        print("  python init-adds.py --dry-run               # Preview only")
        sys.exit(0)
    
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
    
    copy_scaffold(source_dir, args.force, args.dry_run, global_action)
    copy_prompts(source_dir, args.force, args.dry_run, args.no_prompts, global_action)
    copy_docs(source_dir, args.force, args.dry_run, global_action)
    create_app_spec_template(args.dry_run)
    cleanup()
    print_next_steps()


if __name__ == "__main__":
    main()
