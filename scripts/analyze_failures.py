#!/usr/bin/env python3
"""
Analyze failure patterns from training data.

This script identifies common failure patterns and generates insights
for improving the ADDS harness.
"""

import json
from pathlib import Path
from collections import Counter, defaultdict
from datetime import datetime, timedelta
from typing import Dict, List, Any
import argparse


def load_failures(training_data_dir: Path) -> List[Dict[str, Any]]:
    """Load failure data from JSONL file."""
    failures_file = training_data_dir / "failures.jsonl"
    if not failures_file.exists():
        return []
    
    failures = []
    with open(failures_file, 'r') as f:
        for line in f:
            if line.strip():
                failures.append(json.loads(line))
    return failures


def analyze_failure_patterns(failures: List[Dict]) -> Dict[str, Any]:
    """Analyze patterns in failures."""
    if not failures:
        return {"total": 0, "message": "No failures recorded"}
    
    analysis = {
        "total_failures": len(failures),
        "by_type": Counter(),
        "by_category": Counter(),
        "by_severity": Counter(),
        "retry_statistics": defaultdict(list),
        "resolution_times": defaultdict(list),
        "common_patterns": [],
        "prevention_opportunities": []
    }
    
    for failure in failures:
        # Count by type
        analysis["by_type"][failure["failure_type"]] += 1
        
        # Count by category
        category = failure["learning_value"]["category"]
        analysis["by_category"][category] += 1
        
        # Count by severity
        severity = failure["learning_value"]["severity"]
        analysis["by_severity"][severity] += 1
        
        # Track retry statistics
        failure_type = failure["failure_type"]
        retry_count = failure["recovery"]["retry_count"]
        analysis["retry_statistics"][failure_type].append(retry_count)
        
        # Track resolution times
        resolution_time = failure["recovery"]["resolution_time_minutes"]
        analysis["resolution_times"][failure_type].append(resolution_time)
    
    # Find common patterns
    pattern_freq = Counter()
    for failure in failures:
        pattern = failure["learning_value"]["pattern"]
        pattern_freq[pattern] += 1
    
    analysis["common_patterns"] = [
        {"pattern": pattern, "count": count}
        for pattern, count in pattern_freq.most_common(10)
    ]
    
    # Find prevention opportunities
    prevention_suggestions = defaultdict(int)
    for failure in failures:
        if failure["learning_value"]["generalizable"]:
            suggestion = failure["learning_value"]["suggested_prevention"]
            prevention_suggestions[suggestion] += 1
    
    analysis["prevention_opportunities"] = [
        {"suggestion": suggestion, "count": count}
        for suggestion, count in sorted(prevention_suggestions.items(), 
                                        key=lambda x: x[1], reverse=True)[:10]
    ]
    
    # Calculate averages
    analysis["avg_retry_by_type"] = {
        failure_type: {
            "avg_retries": sum(retries) / len(retries),
            "max_retries": max(retries)
        }
        for failure_type, retries in analysis["retry_statistics"].items()
    }
    
    analysis["avg_resolution_time_by_type"] = {
        failure_type: {
            "avg_minutes": sum(times) / len(times),
            "max_minutes": max(times)
        }
        for failure_type, times in analysis["resolution_times"].items()
    }
    
    return analysis


def generate_recommendations(analysis: Dict) -> List[Dict[str, str]]:
    """Generate actionable recommendations based on analysis."""
    recommendations = []
    
    # Check for high-frequency failure types
    if analysis["by_type"]:
        most_common_type = analysis["by_type"].most_common(1)[0]
        if most_common_type[1] >= 3:  # Threshold
            recommendations.append({
                "priority": "high",
                "category": "failure_type",
                "issue": f"High frequency of {most_common_type[0]} failures ({most_common_type[1]} occurrences)",
                "recommendation": f"Consider adding preventive measures for {most_common_type[0]} in harness_config.json",
                "data_source": "failure_type_frequency"
            })
    
    # Check for prevention opportunities
    if analysis["prevention_opportunities"]:
        top_prevention = analysis["prevention_opportunities"][0]
        if top_prevention["count"] >= 2:  # Threshold
            recommendations.append({
                "priority": "medium",
                "category": "prevention",
                "issue": f"Recurring pattern: {top_prevention['suggestion']}",
                "recommendation": "Implement suggested prevention measure",
                "data_source": "prevention_opportunities"
            })
    
    # Check for high retry rates
    if analysis["avg_retry_by_type"]:
        for failure_type, stats in analysis["avg_retry_by_type"].items():
            if stats["avg_retries"] >= 2:
                recommendations.append({
                    "priority": "medium",
                    "category": "retry_rate",
                    "issue": f"High average retry rate for {failure_type}: {stats['avg_retries']:.1f}",
                    "recommendation": "Review and improve auto-recovery mechanisms",
                    "data_source": "retry_statistics"
                })
    
    # Check for long resolution times
    if analysis["avg_resolution_time_by_type"]:
        for failure_type, stats in analysis["avg_resolution_time_by_type"].items():
            if stats["avg_minutes"] >= 30:
                recommendations.append({
                    "priority": "low",
                    "category": "resolution_time",
                    "issue": f"Long average resolution time for {failure_type}: {stats['avg_minutes']:.1f} minutes",
                    "recommendation": "Consider adding diagnostic tools or better error messages",
                    "data_source": "resolution_times"
                })
    
    return recommendations


def generate_report(analysis: Dict, recommendations: List[Dict], 
                   output_file: Path, time_range: str = "all_time") -> None:
    """Generate a human-readable report."""
    report_lines = [
        f"# ADDS Failure Analysis Report",
        f"",
        f"**Time Range**: {time_range}",
        f"**Generated**: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
        f"",
        f"## Summary",
        f"",
        f"- **Total Failures**: {analysis['total_failures']}",
        f"",
    ]
    
    if analysis['total_failures'] == 0:
        report_lines.extend([
            f"No failures recorded. Great job! 🎉",
            f""
        ])
    else:
        # Failure types breakdown
        report_lines.extend([
            f"## Failure Types",
            f"",
            f"| Type | Count | Percentage |",
            f"|------|-------|------------|"
        ])
        
        total = analysis['total_failures']
        for failure_type, count in analysis['by_type'].most_common():
            percentage = (count / total) * 100
            report_lines.append(f"| {failure_type} | {count} | {percentage:.1f}% |")
        
        report_lines.append(f"")
        
        # Common patterns
        if analysis['common_patterns']:
            report_lines.extend([
                f"## Common Failure Patterns",
                f"",
                f"| Pattern | Occurrences |",
                f"|---------|-------------|"
            ])
            
            for pattern in analysis['common_patterns']:
                report_lines.append(f"| {pattern['pattern']} | {pattern['count']} |")
            
            report_lines.append(f"")
        
        # Prevention opportunities
        if analysis['prevention_opportunities']:
            report_lines.extend([
                f"## Prevention Opportunities",
                f"",
                f"| Suggested Prevention | Frequency | Implemented? |",
                f"|---------------------|-----------|--------------|"
            ])
            
            # Check if prevention was implemented (would need to track this in data)
            for opp in analysis['prevention_opportunities'][:5]:
                report_lines.append(f"| {opp['suggestion']} | {opp['count']} | ❓ |")
            
            report_lines.append(f"")
        
        # Recommendations
        if recommendations:
            report_lines.extend([
                f"## Recommendations",
                f""
            ])
            
            for rec in recommendations:
                priority_emoji = {"high": "🔴", "medium": "🟡", "low": "🟢"}
                report_lines.extend([
                    f"### {priority_emoji.get(rec['priority'], '⚪')} {rec['issue']}",
                    f"",
                    f"**Priority**: {rec['priority']}",
                    f"",
                    f"**Recommendation**: {rec['recommendation']}",
                    f"",
                    f"**Data Source**: {rec['data_source']}",
                    f""
                ])
        
        # Resolution time analysis
        if analysis['avg_resolution_time_by_type']:
            report_lines.extend([
                f"## Resolution Time Analysis",
                f"",
                f"| Failure Type | Avg Time (min) | Max Time (min) |",
                f"|--------------|----------------|----------------|"
            ])
            
            for failure_type, stats in analysis['avg_resolution_time_by_type'].items():
                report_lines.append(
                    f"| {failure_type} | {stats['avg_minutes']:.1f} | {stats['max_minutes']:.1f} |"
                )
            
            report_lines.append(f"")
    
    # Write report
    output_file.parent.mkdir(parents=True, exist_ok=True)
    with open(output_file, 'w') as f:
        f.write('\n'.join(report_lines))
    
    print(f"Report generated: {output_file}")


def main():
    parser = argparse.ArgumentParser(description="Analyze ADDS failure patterns")
    parser.add_argument(
        '--project-dir',
        type=Path,
        default=Path.cwd(),
        help='Project directory (default: current directory)'
    )
    parser.add_argument(
        '--output',
        type=Path,
        help='Output report file (default: .ai/reports/failure_analysis_YYYY-MM-DD.md)'
    )
    parser.add_argument(
        '--time-range',
        choices=['week', 'month', 'all_time'],
        default='all_time',
        help='Time range to analyze'
    )
    
    args = parser.parse_args()
    
    training_data_dir = args.project_dir / '.ai' / 'training_data'
    
    if not training_data_dir.exists():
        print(f"Error: Training data directory not found: {training_data_dir}")
        print("Run some development sessions first to collect data.")
        return
    
    # Load and analyze failures
    failures = load_failures(training_data_dir)
    analysis = analyze_failure_patterns(failures)
    recommendations = generate_recommendations(analysis)
    
    # Determine output file
    if args.output:
        output_file = args.output
    else:
        reports_dir = args.project_dir / '.ai' / 'reports'
        date_str = datetime.now().strftime('%Y-%m-%d')
        output_file = reports_dir / f'failure_analysis_{date_str}.md'
    
    # Generate report
    generate_report(analysis, recommendations, output_file, args.time_range)
    
    # Also print summary to console
    print("\n" + "="*60)
    print("FAILURE ANALYSIS SUMMARY")
    print("="*60)
    print(f"Total failures: {analysis['total_failures']}")
    if analysis['by_type']:
        print("\nTop failure types:")
        for failure_type, count in analysis['by_type'].most_common(3):
            print(f"  - {failure_type}: {count}")
    if recommendations:
        print(f"\nGenerated {len(recommendations)} recommendations")
    print("="*60)


if __name__ == '__main__':
    main()
