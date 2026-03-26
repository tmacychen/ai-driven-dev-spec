#!/usr/bin/env python3
"""
ADDS Session Logger

Records session activities to .ai/session_log.jsonl for analytics and debugging.
Each line is a JSON object representing one session event.

Usage:
    python scripts/log_session.py --project-dir . --feature F001 --agent developer --action start
    python scripts/log_session.py --project-dir . --feature F001 --action complete --files-changed 5
    python scripts/log_session.py --project-dir . --feature F001 --action error --error-msg "Build failed"
"""

import argparse
import json
import logging
import os
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional


logger = logging.getLogger(__name__)


def get_session_log_path(project_dir: Path) -> Path:
    """Get the path to session_log.jsonl."""
    return project_dir / '.ai' / 'session_log.jsonl'


def ensure_log_exists(log_path: Path) -> None:
    """Ensure the log file and directory exist."""
    log_path.parent.mkdir(parents=True, exist_ok=True)
    if not log_path.exists():
        log_path.touch()


def read_last_session(log_path: Path) -> Optional[dict]:
    """Read the last session entry to get session_id."""
    if not log_path.exists() or log_path.stat().st_size == 0:
        return None

    with open(log_path, 'r', encoding='utf-8') as f:
        lines = [line.strip() for line in f if line.strip()]
        if not lines:
            return None
        try:
            return json.loads(lines[-1])
        except json.JSONDecodeError:
            return None


def generate_session_id() -> str:
    """Generate a new unique session ID."""
    timestamp = datetime.now(timezone.utc).strftime('%Y%m%d-%H%M%S')
    # Add a random suffix for uniqueness
    import random
    suffix = ''.join(random.choices('abcdefghijklmnopqrstuvwxyz0123456789', k=6))
    return f"{timestamp}-{suffix}"


def get_or_create_session_id(log_path: Path, session_id: Optional[str] = None) -> str:
    """Get existing session ID or create new one."""
    if session_id:
        return session_id

    last_entry = read_last_session(log_path)
    if last_entry and last_entry.get('action') not in ['complete', 'abort']:
        return last_entry.get('session_id', generate_session_id())

    return generate_session_id()


def log_event(
    project_dir: Path,
    feature: str,
    agent: str,
    action: str,
    session_id: Optional[str] = None,
    files_changed: Optional[int] = None,
    tests_run: Optional[int] = None,
    tests_passed: Optional[int] = None,
    error_msg: Optional[str] = None,
    duration_minutes: Optional[int] = None,
    notes: Optional[str] = None
) -> dict:
    """Log a session event to session_log.jsonl."""
    log_path = get_session_log_path(project_dir)
    ensure_log_exists(log_path)

    # Get or generate session ID
    sid = get_or_create_session_id(log_path, session_id)

    # Build event record
    event = {
        'timestamp': datetime.now(timezone.utc).isoformat(),
        'session_id': sid,
        'feature': feature,
        'agent': agent,
        'action': action
    }

    # Add optional fields
    if files_changed is not None:
        event['files_changed'] = files_changed
    if tests_run is not None:
        event['tests_run'] = tests_run
    if tests_passed is not None:
        event['tests_passed'] = tests_passed
    if error_msg is not None:
        event['error'] = error_msg
    if duration_minutes is not None:
        event['duration_minutes'] = duration_minutes
    if notes is not None:
        event['notes'] = notes

    # Append to log
    with open(log_path, 'a', encoding='utf-8') as f:
        f.write(json.dumps(event, ensure_ascii=False) + '\n')

    return event


def show_stats(project_dir: Path) -> None:
    """Show session statistics."""
    log_path = get_session_log_path(project_dir)

    if not log_path.exists():
        logger.info("No session log found.")
        return

    sessions = []
    with open(log_path, 'r', encoding='utf-8') as f:
        for line in f:
            line = line.strip()
            if line:
                try:
                    sessions.append(json.loads(line))
                except json.JSONDecodeError:
                    continue

    if not sessions:
        logger.info("No sessions recorded.")
        return

    # Calculate stats
    total_sessions = len(set(s['session_id'] for s in sessions))
    total_features = len(set(s['feature'] for s in sessions))
    agent_counts = {}
    action_counts = {}
    error_count = 0

    for s in sessions:
        agent = s.get('agent', 'unknown')
        action = s.get('action', 'unknown')
        agent_counts[agent] = agent_counts.get(agent, 0) + 1
        action_counts[action] = action_counts.get(action, 0) + 1
        if 'error' in s:
            error_count += 1

    logger.info("Session Statistics")
    logger.info("=" * 40)
    logger.info(f"Total session events: {len(sessions)}")
    logger.info(f"Unique sessions: {total_sessions}")
    logger.info(f"Features touched: {total_features}")
    logger.info(f"Errors recorded: {error_count}")
    logger.info("")
    logger.info("By Agent:")
    for agent, count in sorted(agent_counts.items()):
        logger.info(f"  {agent}: {count}")
    logger.info("")
    logger.info("By Action:")
    for action, count in sorted(action_counts.items()):
        logger.info(f"  {action}: {count}")


def main():
    parser = argparse.ArgumentParser(description='ADDS Session Logger')
    parser.add_argument('--project-dir', type=str, default='.',
                        help='Project directory (default: current directory)')
    parser.add_argument('--feature', type=str,
                        help='Feature ID (e.g., F001)')
    parser.add_argument('--agent', type=str,
                        choices=['pm', 'architect', 'developer', 'tester', 'reviewer'],
                        help='Agent type')
    parser.add_argument('--action', type=str,
                        choices=['start', 'pause', 'resume', 'complete', 'abort', 'error'],
                        help='Session action')
    parser.add_argument('--session-id', type=str,
                        help='Session ID (auto-generated if not provided)')
    parser.add_argument('--files-changed', type=int,
                        help='Number of files changed')
    parser.add_argument('--tests-run', type=int,
                        help='Number of tests run')
    parser.add_argument('--tests-passed', type=int,
                        help='Number of tests passed')
    parser.add_argument('--error-msg', type=str,
                        help='Error message (for action=error)')
    parser.add_argument('--duration-minutes', type=int,
                        help='Session duration in minutes')
    parser.add_argument('--notes', type=str,
                        help='Additional notes')
    parser.add_argument('--stats', action='store_true',
                        help='Show session statistics')
    parser.add_argument('-v', '--verbose', action='store_true',
                        help='Enable debug output')
    parser.add_argument('-q', '--quiet', action='store_true',
                        help='Suppress info output')

    args = parser.parse_args()

    logging.basicConfig(
        level=logging.DEBUG if args.verbose else (logging.WARNING if args.quiet else logging.INFO),
        format="%(message)s",
        stream=sys.stdout,
        force=True,
    )

    project_dir = Path(args.project_dir).resolve()

    if args.stats:
        show_stats(project_dir)
        return

    # Validate required args for logging
    if not args.action:
        logger.error("--action is required (unless using --stats)")
        sys.exit(1)
    if not args.feature:
        logger.error("--feature is required (unless using --stats)")
        sys.exit(1)
    if not args.agent:
        logger.error("--agent is required (unless using --stats)")
        sys.exit(1)

    # Log the event
    event = log_event(
        project_dir=project_dir,
        feature=args.feature,
        agent=args.agent,
        action=args.action,
        session_id=args.session_id,
        files_changed=args.files_changed,
        tests_run=args.tests_run,
        tests_passed=args.tests_passed,
        error_msg=args.error_msg,
        duration_minutes=args.duration_minutes,
        notes=args.notes
    )

    logger.info(f"Logged: {event['action']} for {event['feature']} by {event['agent']}")
    logger.info(f"   Session: {event['session_id']}")
    logger.info(f"   Time: {event['timestamp']}")


if __name__ == '__main__':
    main()
