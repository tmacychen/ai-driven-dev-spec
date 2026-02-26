#!/usr/bin/env python3
"""
Compress progress.log to maintain context efficiency.

This script addresses the "context window is RAM" insight from Phil Schmid:
When progress.log grows too large, compress it to a summary to reduce
context load for new sessions.
"""

import re
from pathlib import Path
from datetime import datetime, timedelta
from typing import List, Dict, Any
import argparse


def parse_progress_log(progress_file: Path) -> List[Dict[str, Any]]:
    """Parse progress.log into structured entries."""
    if not progress_file.exists():
        return []
    
    with open(progress_file, 'r', encoding='utf-8') as f:
        content = f.read()
    
    # Split by session headers (## [YYYY-MM-DD HH:MM])
    session_pattern = r'## \[(\d{4}-\d{2}-\d{2} \d{2}:\d{2})\]'
    sessions = re.split(session_pattern, content)
    
    entries = []
    # sessions[0] is empty or initial content
    # Then pairs of (timestamp, content)
    for i in range(1, len(sessions), 2):
        if i + 1 < len(sessions):
            timestamp_str = sessions[i]
            session_content = sessions[i + 1]
            
            # Parse timestamp
            try:
                timestamp = datetime.strptime(timestamp_str, '%Y-%m-%d %H:%M')
            except ValueError:
                continue
            
            # Extract key information
            feature_id = extract_feature_id(session_content)
            status = extract_status(session_content)
            
            entries.append({
                'timestamp': timestamp,
                'timestamp_str': timestamp_str,
                'feature_id': feature_id,
                'status': status,
                'content': session_content.strip()
            })
    
    return entries


def extract_feature_id(content: str) -> str:
    """Extract feature ID from session content."""
    match = re.search(r'(?:feat|fix|refactor)-(\w+)', content)
    if match:
        return match.group(1)
    
    # Try alternative patterns
    match = re.search(r'#([A-Z0-9]+)', content)
    if match:
        return match.group(1)
    
    return 'UNKNOWN'


def extract_status(content: str) -> str:
    """Extract status from session content."""
    if '✅' in content or '完成' in content or 'Completed' in content:
        return 'completed'
    elif '❌' in content or '失败' in content or 'Failed' in content:
        return 'failed'
    elif '⚠️' in content or '阻塞' in content or 'Blocked' in content:
        return 'blocked'
    else:
        return 'unknown'


def generate_summary(entries: List[Dict], keep_recent: int = 10) -> str:
    """Generate compressed summary from entries."""
    if not entries:
        return "# Progress Summary\n\nNo entries recorded yet.\n"
    
    summary_lines = [
        "# Progress Summary",
        "",
        f"**Generated**: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
        f"**Total Sessions**: {len(entries)}",
        f"**Showing**: Last {min(keep_recent, len(entries))} sessions in detail, older sessions summarized",
        "",
        "---",
        "",
        "## 📊 Project Statistics",
        ""
    ]
    
    # Calculate statistics
    completed = [e for e in entries if e['status'] == 'completed']
    failed = [e for e in entries if e['status'] == 'failed']
    blocked = [e for e in entries if e['status'] == 'blocked']
    
    summary_lines.extend([
        f"- **Completed Features**: {len(completed)}",
        f"- **Failed Attempts**: {len(failed)}",
        f"- **Blocked Features**: {len(blocked)}",
        f"- **Success Rate**: {len(completed) / len(entries) * 100:.1f}%" if entries else "N/A",
        "",
        "---",
        "",
        "## 📝 Recent Sessions (Detailed)",
        ""
    ])
    
    # Keep recent entries in detail
    recent_entries = entries[-keep_recent:] if len(entries) > keep_recent else entries
    
    for entry in recent_entries:
        summary_lines.extend([
            f"### [{entry['timestamp_str']}] Feature {entry['feature_id']} - {entry['status'].upper()}",
            "",
            entry['content'][:500] + "..." if len(entry['content']) > 500 else entry['content'],
            ""
        ])
    
    # Summarize older entries
    if len(entries) > keep_recent:
        older_entries = entries[:-keep_recent]
        
        summary_lines.extend([
            "---",
            "",
            "## 📜 Historical Summary (Compressed)",
            ""
        ])
        
        # Group by status
        older_completed = [e for e in older_entries if e['status'] == 'completed']
        older_failed = [e for e in older_entries if e['status'] == 'failed']
        
        if older_completed:
            summary_lines.append(f"### Completed Features ({len(older_completed)} sessions)")
            summary_lines.append("")
            for entry in older_completed:
                summary_lines.append(f"- [{entry['timestamp_str']}] {entry['feature_id']}")
            summary_lines.append("")
        
        if older_failed:
            summary_lines.append(f"### Failed/Blocked Features ({len(older_failed)} sessions)")
            summary_lines.append("")
            for entry in older_failed:
                summary_lines.append(f"- [{entry['timestamp_str']}] {entry['feature_id']} - {entry['status']}")
            summary_lines.append("")
    
    # Add key lessons learned
    summary_lines.extend([
        "---",
        "",
        "## 💡 Key Lessons Learned",
        ""
    ])
    
    # Extract lessons from failed entries
    failed_entries = [e for e in entries if e['status'] == 'failed']
    if failed_entries:
        summary_lines.append("### Common Issues:")
        summary_lines.append("")
        for entry in failed_entries[-5:]:  # Last 5 failures
            summary_lines.append(f"- **{entry['feature_id']}** ({entry['timestamp_str']}): {entry['content'][:200]}")
        summary_lines.append("")
    
    summary_lines.extend([
        "---",
        "",
        "## 📋 Next Steps",
        "",
        "See `.ai/feature_list.json` for remaining features and priorities.",
        "",
        "For detailed session history, see `progress.log.archive` (if available).",
        ""
    ])
    
    return '\n'.join(summary_lines)


def compress_progress_log(project_dir: Path, keep_recent: int = 10, 
                          threshold_lines: int = 1000) -> None:
    """Compress progress.log if it exceeds threshold."""
    progress_file = project_dir / 'progress.log'
    
    if not progress_file.exists():
        print("No progress.log found. Nothing to compress.")
        return
    
    # Check file size
    with open(progress_file, 'r', encoding='utf-8') as f:
        lines = f.readlines()
    
    if len(lines) < threshold_lines:
        print(f"progress.log has {len(lines)} lines (threshold: {threshold_lines}). No compression needed.")
        return
    
    print(f"Compressing progress.log ({len(lines)} lines)...")
    
    # Parse entries
    entries = parse_progress_log(progress_file)
    
    if not entries:
        print("No valid entries found in progress.log. Skipping compression.")
        return
    
    # Generate summary
    summary = generate_summary(entries, keep_recent)
    
    # Archive original
    archive_file = project_dir / 'progress.log.archive'
    if archive_file.exists():
        # Append timestamp to existing archive
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        archive_file = project_dir / f'progress.log.archive.{timestamp}'
    
    print(f"Archiving original to: {archive_file}")
    with open(archive_file, 'w', encoding='utf-8') as f:
        f.writelines(lines)
    
    # Write summary
    summary_file = project_dir / 'progress_summary.md'
    print(f"Writing summary to: {summary_file}")
    with open(summary_file, 'w', encoding='utf-8') as f:
        f.write(summary)
    
    # Replace progress.log with recent entries only
    recent_entries = entries[-keep_recent:] if len(entries) > keep_recent else entries
    
    print(f"Writing recent {len(recent_entries)} entries to progress.log...")
    with open(progress_file, 'w', encoding='utf-8') as f:
        f.write("# Progress Log\n\n")
        f.write(f"> **Last {len(recent_entries)} sessions**. ")
        f.write(f"For full history, see `progress.log.archive` or `progress_summary.md`.\n\n")
        
        for entry in recent_entries:
            f.write(f"## [{entry['timestamp_str']}]\n\n")
            f.write(entry['content'] + "\n\n")
    
    print("✅ Compression complete!")
    print(f"   Original: {len(lines)} lines")
    print(f"   Compressed: {sum(1 for _ in open(progress_file))} lines")
    print(f"   Reduction: {(1 - sum(1 for _ in open(progress_file)) / len(lines)) * 100:.1f}%")


def main():
    parser = argparse.ArgumentParser(description="Compress ADDS progress.log to maintain context efficiency")
    parser.add_argument(
        '--project-dir',
        type=Path,
        default=Path.cwd(),
        help='Project directory (default: current directory)'
    )
    parser.add_argument(
        '--keep-recent',
        type=int,
        default=10,
        help='Number of recent sessions to keep in detail (default: 10)'
    )
    parser.add_argument(
        '--threshold',
        type=int,
        default=1000,
        help='Line threshold for compression (default: 1000)'
    )
    parser.add_argument(
        '--force',
        action='store_true',
        help='Force compression regardless of threshold'
    )
    
    args = parser.parse_args()
    
    if args.force:
        print("⚠️ Force mode enabled - compressing regardless of threshold")
        # Temporarily set threshold to 0
        threshold = 0
    else:
        threshold = args.threshold
    
    compress_progress_log(args.project_dir, args.keep_recent, threshold)


if __name__ == '__main__':
    main()
