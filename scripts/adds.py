#!/usr/bin/env python3
"""
ADDS CLI - AI-Driven Development Spec Command Line Interface

Usage:
    adds status          Show project progress statistics
    adds next            Show next feature to develop
    adds validate        Validate feature_list.md format
    adds compress        Compress progress.md context
    adds route           Show current agent role recommendation
    adds archive <F###>  Archive a completed feature
    adds log             Show session log statistics
    adds dag             Visualize dependency graph

Install:
    chmod +x scripts/adds.py
    ln -s $(pwd)/scripts/adds.py /usr/local/bin/adds
    # Or add to PATH:  export PATH="$PATH:/path/to/project/scripts"
"""

import argparse
import json
import os
import re
import sys
import subprocess
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional


ADDS_VERSION = "3.0.0"

VALID_STATUSES = {"pending", "in_progress", "testing", "completed", "blocked", "regression"}
VALID_CATEGORIES = {"core", "feature", "fix", "refactor", "chore", "test", "docs"}
VALID_PRIORITIES = {"high", "medium", "low"}
VALID_COMPLEXITIES = {"low", "medium", "high"}
PRIORITY_ORDER = {"high": 0, "medium": 1, "low": 2}
COMPLEXITY_ORDER = {"low": 0, "medium": 1, "high": 2}


# ─────────────────────────────────────────────────
# Project discovery
# ─────────────────────────────────────────────────

def find_project_root(start: Optional[Path] = None) -> Optional[Path]:
    """Walk up directory tree until we find .ai/"""
    current = Path(start or Path.cwd()).resolve()
    while current != current.parent:
        if (current / ".ai").is_dir():
            return current
        current = current.parent
    return None


def require_project_root() -> Path:
    root = find_project_root()
    if not root:
        print("❌  Not an ADDS project (no .ai/ directory found)", file=sys.stderr)
        sys.exit(1)
    return root


# ─────────────────────────────────────────────────
# Parsers
# ─────────────────────────────────────────────────

def parse_feature_list(project_root: Path) -> Optional[list]:
    """Parse .ai/feature_list.md into a list of feature dicts."""
    path = project_root / ".ai" / "feature_list.md"
    if not path.exists():
        return None

    content = path.read_text(encoding="utf-8")
    features = []

    # Split on feature headers
    sections = re.split(r"(?=^## F\d{3}:)", content, flags=re.MULTILINE)

    for section in sections:
        m = re.match(r"^## (F\d{3}):\s*(.+)", section)
        if not m:
            continue

        fid, title = m.group(1), m.group(2).strip()

        def get_meta(key):
            r = re.search(rf"\*\*{key}\*\*:\s*(.+)", section)
            return r.group(1).strip() if r else None

        deps_raw = get_meta("Dependencies")
        deps = (
            [d.strip() for d in deps_raw.split(",") if d.strip() and d.strip() != "-"]
            if deps_raw else []
        )

        features.append({
            "id": fid,
            "title": title,
            "category": get_meta("Category") or "unknown",
            "priority": get_meta("Priority") or "medium",
            "status": get_meta("Status") or "pending",
            "complexity": get_meta("Complexity") or "medium",
            "dependencies": deps,
        })

    return features


def parse_progress(project_root: Path) -> dict:
    path = project_root / ".ai" / "progress.md"
    if not path.exists():
        return {"sessions": 0, "last_session": None, "lines": 0}
    content = path.read_text(encoding="utf-8")
    sessions = len(re.findall(r"^## Session", content, re.MULTILINE))
    last_m = re.search(r"^## Session\s+([\d-]+ [\d:]+)", content, re.MULTILINE)
    return {
        "sessions": sessions,
        "last_session": last_m.group(1) if last_m else None,
        "lines": len(content.splitlines()),
    }


def parse_session_log(project_root: Path) -> dict:
    path = project_root / ".ai" / "session_log.jsonl"
    by_agent: dict = defaultdict(int)
    by_action: dict = defaultdict(int)
    entries = 0
    if path.exists():
        for line in path.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if not line:
                continue
            try:
                obj = json.loads(line)
                by_agent[obj.get("agent", "unknown")] += 1
                by_action[obj.get("action", "unknown")] += 1
                entries += 1
            except json.JSONDecodeError:
                pass
    return {"entries": entries, "by_agent": dict(by_agent), "by_action": dict(by_action)}


# ─────────────────────────────────────────────────
# DAG logic
# ─────────────────────────────────────────────────

def detect_cycles(features: list) -> list:
    """Return a list of cycle paths (each path is a list of feature IDs)."""
    valid_ids = {f["id"] for f in features}
    graph = {f["id"]: [d for d in f["dependencies"] if d in valid_ids] for f in features}

    cycles = []
    visited = set()
    rec_stack = set()

    def dfs(node, path):
        if node in rec_stack:
            idx = path.index(node)
            cycles.append(path[idx:] + [node])
            return
        if node in visited:
            return
        visited.add(node)
        rec_stack.add(node)
        for nbr in graph.get(node, []):
            dfs(nbr, path + [node])
        rec_stack.discard(node)

    for f in features:
        if f["id"] not in visited:
            dfs(f["id"], [])

    return cycles


def find_next_feature(features: list) -> Optional[dict]:
    """Return the highest-priority pending feature whose deps are all completed."""
    completed = {f["id"] for f in features if f["status"] == "completed"}
    ready = [
        f for f in features
        if f["status"] == "pending" and all(d in completed for d in f["dependencies"])
    ]
    if not ready:
        return None
    ready.sort(key=lambda f: (
        PRIORITY_ORDER.get(f["priority"], 99),
        COMPLEXITY_ORDER.get(f["complexity"], 99),
    ))
    return ready[0]


def determine_agent_role(features: list) -> dict:
    """Apply the ADDS Agent Selection Logic decision tree."""
    for f in features:
        if f["status"] in ("blocked", "regression"):
            return {"agent": "developer", "reason": f"Feature {f['id']} is {f['status']}",
                    "prompt": "developer_prompt.md"}

    for f in features:
        if f["status"] == "testing":
            return {"agent": "tester", "reason": f"Feature {f['id']} is ready for testing",
                    "prompt": "tester_prompt.md"}

    for f in features:
        if f["status"] == "in_progress":
            return {"agent": "developer", "reason": f"Feature {f['id']} is in progress",
                    "prompt": "developer_prompt.md"}

    nxt = find_next_feature(features)
    if nxt:
        return {"agent": "developer", "reason": f"Feature {nxt['id']} is next to implement",
                "prompt": "developer_prompt.md"}

    if features and all(f["status"] == "completed" for f in features):
        return {"agent": "reviewer", "reason": "All features completed, ready for review",
                "prompt": "reviewer_prompt.md"}

    return {"agent": "pm", "reason": "No features found or project initialization needed",
            "prompt": "pm_prompt.md"}


# ─────────────────────────────────────────────────
# Commands
# ─────────────────────────────────────────────────

def cmd_status(args):
    root = require_project_root()
    features = parse_feature_list(root) or []
    progress = parse_progress(root)
    log = parse_session_log(root)

    counts = defaultdict(int)
    for f in features:
        counts[f["status"]] += 1

    total = len(features)
    done = counts["completed"]
    pct = round(done / total * 100) if total else 0

    if args.json:
        print(json.dumps({
            "project": str(root),
            "features": {
                "total": total,
                "pending": counts["pending"],
                "in_progress": counts["in_progress"],
                "testing": counts["testing"],
                "completed": done,
                "blocked": counts["blocked"],
                "regression": counts["regression"],
            },
            "progress_pct": pct,
            "sessions": progress["sessions"],
            "last_session": progress["last_session"],
            "progress_lines": progress["lines"],
            "log_entries": log["entries"],
        }, indent=2))
        return

    bar_width = 30
    filled = round(bar_width * pct / 100)
    bar = "█" * filled + "░" * (bar_width - filled)

    print("📊 ADDS Project Status")
    print("─" * 42)
    print(f"  Project:     {root}")
    print(f"  Total:       {total}")
    print(f"  Pending:     {counts['pending']}")
    print(f"  In Progress: {counts['in_progress']}")
    print(f"  Testing:     {counts['testing']}")
    print(f"  Completed:   {done}")
    if counts["blocked"]:
        print(f"  Blocked:     {counts['blocked']}")
    if counts["regression"]:
        print(f"  Regression:  {counts['regression']}")
    print()
    print(f"  Progress: [{bar}] {pct}%  ({done}/{total})")
    print()
    print(f"  Sessions:      {progress['sessions']}")
    if progress["last_session"]:
        print(f"  Last Session:  {progress['last_session']}")
    if progress["lines"] > 800:
        print(f"  ⚠️  progress.md has {progress['lines']} lines — consider running: adds compress")
    if log["entries"]:
        print(f"  Log Entries:   {log['entries']}")


def cmd_next(args):
    root = require_project_root()
    features = parse_feature_list(root)
    if not features:
        print("No features found. Create .ai/feature_list.md first.")
        return

    nxt = find_next_feature(features)

    if args.json:
        print(json.dumps(nxt, indent=2))
        return

    if not nxt:
        print("✅  No pending features ready to implement.")
        blocked = [f for f in features if f["status"] == "blocked"]
        if blocked:
            print(f"\n⚠️  {len(blocked)} feature(s) blocked:")
            for f in blocked:
                print(f"   - {f['id']}: {f['title']}")
        return

    print("🎯 Next Feature to Implement")
    print("─" * 42)
    print(f"  ID:          {nxt['id']}")
    print(f"  Title:       {nxt['title']}")
    print(f"  Priority:    {nxt['priority']}")
    print(f"  Complexity:  {nxt['complexity']}")
    print(f"  Category:    {nxt['category']}")
    if nxt["dependencies"]:
        print(f"  Deps:        {', '.join(nxt['dependencies'])}")
    print()
    print(f"  → Open .ai/prompts/developer_prompt.md and implement {nxt['id']}")


def cmd_validate(args):
    root = require_project_root()
    features = parse_feature_list(root)
    if features is None:
        print("❌  .ai/feature_list.md not found", file=sys.stderr)
        sys.exit(1)

    errors = []
    warnings = []
    valid_ids = {f["id"] for f in features}

    # Duplicate IDs
    ids = [f["id"] for f in features]
    seen = set()
    for fid in ids:
        if fid in seen:
            errors.append(f"Duplicate feature ID: {fid}")
        seen.add(fid)

    for f in features:
        prefix = f["id"]

        # Missing dependencies
        for dep in f["dependencies"]:
            if dep not in valid_ids:
                errors.append(f"{prefix}: dependency '{dep}' does not exist")

        # Invalid field values
        if f["category"] not in VALID_CATEGORIES:
            errors.append(f"{prefix}: invalid category '{f['category']}'")
        if f["priority"] not in VALID_PRIORITIES:
            errors.append(f"{prefix}: invalid priority '{f['priority']}'")
        if f["status"] not in VALID_STATUSES:
            errors.append(f"{prefix}: invalid status '{f['status']}'")

        # Completed but dependency is not
        if f["status"] == "completed":
            for dep in f["dependencies"]:
                dep_feat = next((x for x in features if x["id"] == dep), None)
                if dep_feat and dep_feat["status"] != "completed":
                    warnings.append(f"{prefix}: marked completed but dep {dep} is '{dep_feat['status']}'")

    # Cycle detection
    for cycle in detect_cycles(features):
        errors.append(f"Circular dependency: {' → '.join(cycle)}")

    valid = len(errors) == 0

    if args.json:
        print(json.dumps({"valid": valid, "errors": errors, "warnings": warnings}, indent=2))
        sys.exit(0 if valid else 1)

    if valid and not warnings:
        print(f"✅  feature_list.md is valid ({len(features)} features)")
    else:
        if errors:
            print(f"❌  {len(errors)} error(s):")
            for e in errors:
                print(f"   - {e}")
        if warnings:
            print(f"⚠️   {len(warnings)} warning(s):")
            for w in warnings:
                print(f"   - {w}")
    sys.exit(0 if valid else 1)


def cmd_compress(args):
    root = require_project_root()
    script = root / "scripts" / "compress_context.py"
    if not script.exists():
        print("❌  compress_context.py not found", file=sys.stderr)
        sys.exit(1)
    result = subprocess.run(
        [sys.executable, str(script), "--project-dir", str(root)],
        check=False
    )
    sys.exit(result.returncode)


def cmd_route(args):
    root = require_project_root()
    features = parse_feature_list(root)

    if not features:
        result = {"agent": "pm", "prompt": "pm_prompt.md",
                  "reason": "No feature_list.md — project initialization needed"}
    else:
        result = determine_agent_role(features)

    if args.json:
        print(json.dumps(result, indent=2))
        return

    agent_labels = {
        "pm": "PM Agent",
        "architect": "Architect Agent",
        "developer": "Developer Agent",
        "tester": "Tester Agent",
        "reviewer": "Reviewer Agent",
    }
    print("🧭 Agent Recommendation")
    print("─" * 42)
    print(f"  Agent:  {agent_labels.get(result['agent'], result['agent'])}")
    print(f"  Prompt: .ai/prompts/{result['prompt']}")
    print(f"  Reason: {result['reason']}")
    print()
    print("  Next Steps:")
    print(f"    1. Read .ai/prompts/{result['prompt']}")
    print("    2. Read .ai/feature_list.md for current state")
    print("    3. Follow the prompt instructions")


def cmd_archive(args):
    root = require_project_root()
    fid = args.feature_id.upper()
    if not re.match(r"^F\d{3}$", fid):
        print(f"❌  Invalid feature ID '{fid}' — expected format: F001", file=sys.stderr)
        sys.exit(1)

    feature_list_path = root / ".ai" / "feature_list.md"
    if not feature_list_path.exists():
        print("❌  .ai/feature_list.md not found", file=sys.stderr)
        sys.exit(1)

    content = feature_list_path.read_text(encoding="utf-8")

    # Find the feature section
    pattern = re.compile(
        rf"(^## {re.escape(fid)}:.*?)(?=^## F\d{{3}}:|\Z)",
        re.MULTILINE | re.DOTALL
    )
    m = pattern.search(content)
    if not m:
        print(f"❌  Feature {fid} not found in feature_list.md", file=sys.stderr)
        sys.exit(1)

    feature_section = m.group(0)

    # Check status
    if "**Status**: completed" not in feature_section:
        status_m = re.search(r"\*\*Status\*\*:\s*(\w+)", feature_section)
        current = status_m.group(1) if status_m else "unknown"
        print(f"❌  Feature {fid} is '{current}', not 'completed'", file=sys.stderr)
        print("   Only completed features can be archived.", file=sys.stderr)
        sys.exit(1)

    # Create archive
    archive_dir = root / ".ai" / "archive"
    archive_dir.mkdir(parents=True, exist_ok=True)
    archive_file = archive_dir / f"{fid}.md"

    archived_at = datetime.now(timezone.utc).isoformat()
    archive_content = f"# Archived Feature\n\n**Archived**: {archived_at}\n\n---\n\n{feature_section.strip()}\n"
    archive_file.write_text(archive_content, encoding="utf-8")

    # Remove from feature_list.md
    new_content = pattern.sub("", content).strip() + "\n"
    feature_list_path.write_text(new_content, encoding="utf-8")

    print(f"✅  Archived {fid} → .ai/archive/{fid}.md")
    print(f"   Removed from feature_list.md")


def cmd_log(args):
    root = require_project_root()
    log = parse_session_log(root)

    if args.json:
        print(json.dumps(log, indent=2))
        return

    print("📋 Session Log Statistics")
    print("─" * 42)
    print(f"  Total Entries: {log['entries']}")
    if log["by_agent"]:
        print("\n  By Agent:")
        for agent, count in sorted(log["by_agent"].items()):
            print(f"    {agent}: {count}")
    if log["by_action"]:
        print("\n  By Action:")
        for action, count in sorted(log["by_action"].items()):
            print(f"    {action}: {count}")


def cmd_dag(args):
    """Visualize dependency graph as ASCII art."""
    root = require_project_root()
    features = parse_feature_list(root)
    if not features:
        print("No features found.")
        return

    valid_ids = {f["id"] for f in features}
    feature_map = {f["id"]: f for f in features}

    STATUS_ICONS = {
        "pending": "○",
        "in_progress": "◉",
        "testing": "◎",
        "completed": "●",
        "blocked": "✗",
        "regression": "⚠",
    }

    # Find root nodes (no dependencies)
    has_parent = set()
    for f in features:
        for dep in f["dependencies"]:
            if dep in valid_ids:
                has_parent.add(f["id"])

    roots = [f for f in features if f["id"] not in has_parent]

    cycles = detect_cycles(features)
    if cycles:
        print("⚠️  Circular dependencies detected:")
        for c in cycles:
            print(f"   {' → '.join(c)}")
        print()

    print("🔗 Dependency Graph")
    print("─" * 42)

    printed = set()

    def print_tree(fid, indent=0, last=True):
        if fid in printed:
            prefix = "  " * indent + ("└── " if last else "├── ")
            f = feature_map.get(fid)
            if f:
                icon = STATUS_ICONS.get(f["status"], "?")
                print(f"{prefix}{icon} {fid} (↑ already shown)")
            return
        printed.add(fid)
        f = feature_map.get(fid)
        if not f:
            return
        icon = STATUS_ICONS.get(f["status"], "?")
        prefix = "  " * indent + ("└── " if (indent > 0 and last) else ("├── " if indent > 0 else ""))
        print(f"{prefix}{icon} {f['id']}: {f['title']}  [{f['status']}]")

        # Find children
        children = [x for x in features if fid in x["dependencies"]]
        for i, child in enumerate(children):
            print_tree(child["id"], indent + 1, last=(i == len(children) - 1))

    for root_feat in roots:
        print_tree(root_feat["id"])

    # Legend
    print()
    print("  Legend: ○ pending  ◉ in_progress  ◎ testing  ● completed  ✗ blocked  ⚠ regression")


# ─────────────────────────────────────────────────
# Branch commands (P3-4.4 Parallel dev support)
# ─────────────────────────────────────────────────

def _get_git_branch() -> Optional[str]:
    """Return current git branch name, or None."""
    try:
        result = subprocess.run(
            ["git", "rev-parse", "--abbrev-ref", "HEAD"],
            capture_output=True, text=True, check=True
        )
        return result.stdout.strip()
    except (subprocess.CalledProcessError, FileNotFoundError):
        return None


def _branch_progress_path(root: Path, branch: Optional[str] = None) -> Path:
    """Return the branch-scoped progress file path."""
    if branch is None:
        branch = _get_git_branch()
    if branch and branch not in ("main", "master", "HEAD"):
        safe = re.sub(r"[^\w\-]", "_", branch)
        return root / ".ai" / "branches" / f"progress_{safe}.md"
    return root / ".ai" / "progress.md"


def cmd_branch(args):
    root = require_project_root()
    subcmd = args.branch_cmd

    if subcmd == "status":
        branch = _get_git_branch()
        progress_path = _branch_progress_path(root, branch)
        branches_dir = root / ".ai" / "branches"

        print("🌿 Branch Status")
        print("─" * 42)
        print(f"  Current branch:  {branch or '(unknown)'}")
        print(f"  Progress file:   {progress_path.relative_to(root)}")
        print(f"  File exists:     {'yes' if progress_path.exists() else 'no'}")
        print()

        if branches_dir.exists():
            branch_files = list(branches_dir.glob("progress_*.md"))
            if branch_files:
                print("  Branch progress files:")
                for bf in sorted(branch_files):
                    lines = len(bf.read_text(encoding="utf-8").splitlines())
                    print(f"    {bf.name}  ({lines} lines)")

    elif subcmd == "init":
        branch = _get_git_branch()
        if not branch or branch in ("main", "master", "HEAD"):
            print("❌  Cannot init branch progress on main/master. Create a feature branch first.")
            sys.exit(1)
        progress_path = _branch_progress_path(root, branch)
        progress_path.parent.mkdir(parents=True, exist_ok=True)
        if progress_path.exists() and not getattr(args, "force", False):
            print(f"⚠️   Branch progress file already exists: {progress_path.relative_to(root)}")
            print("    Use --force to overwrite.")
            sys.exit(1)
        feature_id = getattr(args, "feature_id", None) or ""
        content = (
            f"# Branch Progress: {branch}\n\n"
            f"> Created: {datetime.now(timezone.utc).isoformat()}\n"
            f"> Feature: {feature_id or 'TBD'}\n\n"
            "---\n\n"
            "## Session Log\n\n"
            "_(sessions will be appended here)_\n"
        )
        progress_path.write_text(content, encoding="utf-8")
        print(f"✅  Created branch progress: {progress_path.relative_to(root)}")

    elif subcmd == "merge-check":
        # Show merge conflicts risk for feature_list.md across branches
        branch = _get_git_branch()
        branches_dir = root / ".ai" / "branches"
        print("🔍 Merge Risk Check")
        print("─" * 42)
        print(f"  Current branch: {branch or '(unknown)'}")
        print()
        if not branches_dir.exists() or not list(branches_dir.glob("progress_*.md")):
            print("  No branch progress files found. Nothing to check.")
            return
        # Check git status for .ai/feature_list.md
        try:
            result = subprocess.run(
                ["git", "log", "--oneline", "-5", "--", ".ai/feature_list.md"],
                capture_output=True, text=True, cwd=str(root)
            )
            if result.stdout.strip():
                print("  Recent feature_list.md changes (last 5):")
                for line in result.stdout.strip().splitlines():
                    print(f"    {line}")
            else:
                print("  No recent changes to feature_list.md")
        except (subprocess.CalledProcessError, FileNotFoundError):
            print("  (git not available)")
        print()
        print("  Tip: Run `adds validate` before merging to catch conflicts early.")

    elif subcmd == "list":
        branches_dir = root / ".ai" / "branches"
        if not branches_dir.exists():
            print("No branch progress files found.")
            return
        files = list(branches_dir.glob("progress_*.md"))
        if not files:
            print("No branch progress files found.")
            return
        print("🌿 Branch Progress Files")
        print("─" * 42)
        for bf in sorted(files):
            lines = len(bf.read_text(encoding="utf-8").splitlines())
            branch_name = bf.stem.replace("progress_", "").replace("_", "/", 1)
            print(f"  {branch_name:30s}  {lines} lines")




# ─────────────────────────────────────────────────
# Entry point
# ─────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(
        prog="adds",
        description=f"ADDS CLI v{ADDS_VERSION} — AI-Driven Development Spec",
    )
    parser.add_argument("--version", action="version", version=f"ADDS CLI v{ADDS_VERSION}")
    sub = parser.add_subparsers(dest="command", metavar="<command>")

    # status
    p = sub.add_parser("status", help="Show project progress statistics")
    p.add_argument("-j", "--json", action="store_true", help="Output as JSON")

    # next
    p = sub.add_parser("next", help="Show next feature to develop")
    p.add_argument("-j", "--json", action="store_true", help="Output as JSON")

    # validate
    p = sub.add_parser("validate", help="Validate feature_list.md format")
    p.add_argument("-j", "--json", action="store_true", help="Output as JSON")

    # compress
    sub.add_parser("compress", help="Compress progress.md context")

    # route
    p = sub.add_parser("route", help="Show current agent role recommendation")
    p.add_argument("-j", "--json", action="store_true", help="Output as JSON")

    # archive
    p = sub.add_parser("archive", help="Archive a completed feature")
    p.add_argument("feature_id", metavar="F###", help="Feature ID to archive (e.g. F001)")

    # log
    p = sub.add_parser("log", help="Show session log statistics")
    p.add_argument("-j", "--json", action="store_true", help="Output as JSON")

    # dag
    sub.add_parser("dag", help="Visualize feature dependency graph")

    # branch
    bp = sub.add_parser("branch", help="Multi-branch parallel development support")
    branch_sub = bp.add_subparsers(dest="branch_cmd", metavar="<subcommand>")
    branch_sub.add_parser("status", help="Show branch progress status")
    bi = branch_sub.add_parser("init", help="Initialize progress file for current branch")
    bi.add_argument("feature_id", metavar="F###", nargs="?", help="Feature being worked on")
    bi.add_argument("--force", action="store_true", help="Overwrite existing branch progress")
    branch_sub.add_parser("list", help="List all branch progress files")
    branch_sub.add_parser("merge-check", help="Check merge risk for feature_list.md")

    args = parser.parse_args()

    dispatch = {
        "status":   cmd_status,
        "next":     cmd_next,
        "validate": cmd_validate,
        "compress": cmd_compress,
        "route":    cmd_route,
        "archive":  cmd_archive,
        "log":      cmd_log,
        "dag":      cmd_dag,
        "branch":   cmd_branch,
    }

    if args.command not in dispatch:
        parser.print_help()
        sys.exit(0)

    dispatch[args.command](args)


if __name__ == "__main__":
    main()
