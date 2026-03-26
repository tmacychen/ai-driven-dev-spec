#!/usr/bin/env python3
"""
ADDS Security Hook — pre-commit

Intercepts and blocks forbidden commands that AI Agents may attempt
to commit in scripts, shell files, or Makefiles.

Install:
    cp scripts/adds_security_hook.py .git/hooks/pre-commit
    chmod +x .git/hooks/pre-commit

Or use install_hooks.py to install automatically:
    python3 scripts/install_hooks.py
"""

import logging
import re
import subprocess
import sys
from pathlib import Path


logger = logging.getLogger(__name__)

# ─────────────────────────────────────────────────────────
# Security Rules
# ─────────────────────────────────────────────────────────

FORBIDDEN_PATTERNS = [
    # Privilege escalation
    (r"\bsudo\s", "sudo — privilege escalation"),  # adds-security: allow
    (r"\bsu\s+-", "su — user switching"),  # adds-security: allow

    # Destructive system commands
    (r"\brm\s+.*-[a-zA-Z]*r[a-zA-Z]*f\s+/", "rm -rf / — root filesystem deletion"),  # adds-security: allow
    (r"\bmkfs\b", "mkfs — filesystem formatting"),  # adds-security: allow
    (r"\bfdisk\b", "fdisk — disk partitioning"),  # adds-security: allow
    (r"\bdd\s+if=.*of=/dev/", "dd to block device — data destruction risk"),  # adds-security: allow

    # Unreviewed script execution
    (r"curl\s+.*\|.*sh\b", "curl | sh — unreviewed script execution"),  # adds-security: allow
    (r"curl\s+.*\|.*bash\b", "curl | bash — unreviewed script execution"),  # adds-security: allow
    (r"wget\s+.*\|.*sh\b", "wget | sh — unreviewed script execution"),  # adds-security: allow
    (r"wget\s+.*\|.*bash\b", "wget | bash — unreviewed script execution"),  # adds-security: allow

    # Network backdoors
    (r"\bnc\s+-l\b", "nc -l — network listener (backdoor risk)"),  # adds-security: allow
    (r"\bnetcat\b", "netcat — network backdoor risk"),  # adds-security: allow
    (r"\btelnet\b", "telnet — unencrypted network access"),  # adds-security: allow

    # Network config changes
    (r"\biptables\s+-[A-Z]", "iptables — firewall rule modification"),  # adds-security: allow
    (r"\broute\s+(add|del)\b", "route add/del — routing table modification"),  # adds-security: allow

    # Permission changes (likely unnecessary in projects)
    (r"\bchmod\s+[0-7]*7[0-7][0-7]\b", "chmod 7xx — world-writable permission"),  # adds-security: allow
    (r"\bchown\s+root\b", "chown root — ownership to root"),  # adds-security: allow

    # System process signals
    (r"\bkill\s+-9\s+1\b", "kill -9 1 — killing init process"),  # adds-security: allow
    (r"\bkillall\b", "killall — mass process termination"),  # adds-security: allow
]

# File extensions to scan
SCAN_EXTENSIONS = {
    ".sh", ".bash", ".zsh", ".fish",
    ".py", ".js", ".ts", ".rb",
    "Makefile", "Dockerfile",
    ".yml", ".yaml",
}

# Bypass marker — allow a line by adding this comment
BYPASS_MARKER = "# adds-security: allow"

# Log file location
HOOK_LOG = Path(".ai") / "security_hook.log"


def get_staged_files() -> list:
    """Return list of staged file paths."""
    result = subprocess.run(
        ["git", "diff", "--cached", "--name-only", "--diff-filter=ACMR"],
        capture_output=True, text=True
    )
    return [p for p in result.stdout.splitlines() if p.strip()]


def should_scan(filepath: str) -> bool:
    """Decide whether to scan this file."""
    p = Path(filepath)
    if p.name in SCAN_EXTENSIONS:
        return True
    return p.suffix.lower() in SCAN_EXTENSIONS


def scan_content(content: str, filepath: str) -> list:
    """
    Scan file content for forbidden patterns.
    Returns list of (line_num, line, reason).
    """
    violations = []
    for line_num, line in enumerate(content.splitlines(), 1):
        # Skip commented-out lines and bypass markers
        stripped = line.strip()
        if stripped.startswith("#") or BYPASS_MARKER in line:
            continue

        for pattern, reason in FORBIDDEN_PATTERNS:
            if re.search(pattern, line):
                violations.append((line_num, line.rstrip(), reason))
                break  # Only report first match per line

    return violations


def log_violation(filepath: str, violations: list) -> None:
    """Append violation to security log. Ensure directory exists and fall back to stderr on failure."""
    try:
        # Ensure the parent directory exists (create .ai/ if needed)
        HOOK_LOG.parent.mkdir(parents=True, exist_ok=True)
        from datetime import datetime, timezone
        timestamp = datetime.now(timezone.utc).isoformat()
        with open(HOOK_LOG, "a", encoding="utf-8") as f:
            for line_num, line, reason in violations:
                f.write(f"{timestamp}\tBLOCKED\t{filepath}:{line_num}\t{reason}\t{line[:80]}\n")
    except Exception:
        # Non-fatal — log the failure via logging module, do not block the commit
        logger.error("Failed to write security hook log to %s", HOOK_LOG)
        try:
            from datetime import datetime, timezone
            ts = datetime.now(timezone.utc).isoformat()
            for line_num, line, reason in violations:
                sys.stderr.write(f"{ts}\tLOG_FAILURE\t{filepath}:{line_num}\t{reason}\t{line[:80]}\n")
        except Exception:
            # Give up silently to avoid blocking commits
            pass


def main():
    # Configure logging for internal diagnostics (main output uses print() for git hook compatibility)
    logging.basicConfig(
        level=logging.WARNING,
        format="%(message)s",
        stream=sys.stderr,
        force=True,
    )

    staged = get_staged_files()
    if not staged:
        sys.exit(0)

    all_violations = {}

    for filepath in staged:
        if not should_scan(filepath):
            continue
        p = Path(filepath)
        if not p.exists():
            continue
        try:
            content = p.read_text(encoding="utf-8", errors="ignore")
        except OSError:
            continue

        violations = scan_content(content, filepath)
        if violations:
            all_violations[filepath] = violations

    if not all_violations:
        sys.exit(0)

    # Block the commit — use print() directly for git hook output compatibility
    print()
    print("🔒 ADDS Security Hook — Commit Blocked")
    print("=" * 50)
    print()
    print("The following forbidden patterns were detected:")
    print()

    for filepath, violations in all_violations.items():
        print(f"  📄 {filepath}")
        for line_num, line, reason in violations:
            print(f"     Line {line_num}: {reason}")
            print(f"     > {line[:80]}")
        print()
        log_violation(filepath, violations)

    print("─" * 50)
    print()
    print("To fix:")
    print("  1. Remove the forbidden command from the file")
    print("  2. Or if intentional, add the bypass marker on that line:")
    print(f"     {BYPASS_MARKER}")
    print()
    print("Security policy: docs/guide/05-security.md")
    print()

    sys.exit(1)


if __name__ == "__main__":
    main()
