#!/usr/bin/env python3
"""
Generate performance metrics from ADDS sessions.

This script calculates key performance indicators for the harness
and generates a comprehensive metrics report.
"""

import json
from pathlib import Path
from datetime import datetime
from typing import Dict, List, Any
import argparse


def load_feature_list(project_dir: Path) -> Dict[str, Any]:
    """Load feature list."""
    feature_file = project_dir / '.ai' / 'feature_list.json'
    if not feature_file.exists():
        return {}
    
    with open(feature_file, 'r') as f:
        return json.load(f)


def load_performance_data(training_data_dir: Path) -> List[Dict[str, Any]]:
    """Load performance metrics from JSONL file."""
    perf_file = training_data_dir / "performance.jsonl"
    if not perf_file.exists():
        return []
    
    performance = []
    with open(perf_file, 'r') as f:
        for line in f:
            if line.strip():
                performance.append(json.loads(line))
    return performance


def calculate_reliability_metrics(feature_list: List[Dict], 
                                  performance_data: List[Dict]) -> Dict[str, Any]:
    """Calculate reliability metrics."""
    if not feature_list:
        return {}
    
    total_features = len(feature_list)
    completed_features = len([f for f in feature_list if f.get('passes', False)])
    blocked_features = len([f for f in feature_list if f.get('status') == 'blocked'])
    regression_features = len([f for f in feature_list if f.get('status') == 'regression'])
    
    # Calculate retry rate from performance data
    total_retries = sum(p.get('reliability', {}).get('retry_count', 0) 
                       for p in performance_data)
    
    return {
        "task_completion_rate": {
            "value": (completed_features / total_features * 100) if total_features > 0 else 0,
            "formula": f"{completed_features}/{total_features}",
            "target": ">= 90%"
        },
        "regression_rate": {
            "value": (regression_features / completed_features * 100) if completed_features > 0 else 0,
            "formula": f"{regression_features}/{completed_features}",
            "target": "<= 5%"
        },
        "blocked_rate": {
            "value": (blocked_features / total_features * 100) if total_features > 0 else 0,
            "formula": f"{blocked_features}/{total_features}",
            "target": "<= 10%"
        },
        "retry_rate": {
            "value": (total_retries / len(performance_data)) if performance_data else 0,
            "formula": f"{total_retries}/{len(performance_data)}",
            "target": "<= 0.5"
        }
    }


def calculate_efficiency_metrics(performance_data: List[Dict]) -> Dict[str, Any]:
    """Calculate efficiency metrics."""
    if not performance_data:
        return {}
    
    # Time efficiency
    time_data = [p.get('timing', {}) for p in performance_data]
    
    estimated_times = [t.get('estimated_minutes', 0) for t in time_data if t.get('estimated_minutes')]
    actual_times = [t.get('actual_minutes', 0) for t in time_data if t.get('actual_minutes')]
    efficiency_ratios = [t.get('efficiency_ratio', 0) for t in time_data if t.get('efficiency_ratio')]
    
    # Context usage
    context_tokens = [p.get('efficiency', {}).get('context_tokens_used', 0) 
                     for p in performance_data]
    
    return {
        "average_development_time": {
            "value": sum(actual_times) / len(actual_times) if actual_times else 0,
            "unit": "minutes",
            "target": "As per estimate"
        },
        "estimation_accuracy": {
            "value": sum(efficiency_ratios) / len(efficiency_ratios) if efficiency_ratios else 0,
            "formula": "actual/estimated",
            "interpretation": ">1 = faster than estimated, <1 = slower",
            "target": "0.8 - 1.2"
        },
        "average_context_usage": {
            "value": sum(context_tokens) / len(context_tokens) if context_tokens else 0,
            "unit": "tokens",
            "target": "< 100,000"
        }
    }


def calculate_quality_metrics(feature_list: List[Dict], 
                             performance_data: List[Dict]) -> Dict[str, Any]:
    """Calculate quality metrics."""
    if not performance_data:
        return {}
    
    # Extract quality metrics
    test_coverages = []
    lint_errors = []
    
    for p in performance_data:
        quality = p.get('quality', {})
        
        # Parse test coverage (remove %)
        coverage = quality.get('test_coverage', '0%')
        if isinstance(coverage, str) and coverage.endswith('%'):
            test_coverages.append(float(coverage[:-1]))
        elif isinstance(coverage, (int, float)):
            test_coverages.append(coverage)
        
        lint_errors.append(quality.get('lint_errors', 0))
    
    return {
        "average_test_coverage": {
            "value": sum(test_coverages) / len(test_coverages) if test_coverages else 0,
            "unit": "%",
            "target": ">= 70%"
        },
        "average_lint_errors": {
            "value": sum(lint_errors) / len(lint_errors) if lint_errors else 0,
            "unit": "errors per feature",
            "target": "0"
        },
        "zero_lint_rate": {
            "value": (lint_errors.count(0) / len(lint_errors) * 100) if lint_errors else 0,
            "unit": "%",
            "target": "100%"
        }
    }


def generate_metrics_report(reliability: Dict, efficiency: Dict, quality: Dict,
                           output_file: Path, project_dir: Path) -> None:
    """Generate comprehensive metrics report."""
    
    # Load feature list for context
    feature_list = load_feature_list(project_dir)
    
    report_lines = [
        f"# ADDS Performance Metrics Report",
        f"",
        f"**Generated**: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
        f"**Project**: {project_dir.name}",
        f"",
        f"## 📊 Overall Score",
        f"",
    ]
    
    # Calculate overall score
    scores = []
    if reliability.get('task_completion_rate'):
        scores.append(reliability['task_completion_rate']['value'])
    if quality.get('average_test_coverage'):
        scores.append(quality['average_test_coverage']['value'])
    
    overall_score = sum(scores) / len(scores) if scores else 0
    score_emoji = "🟢" if overall_score >= 80 else "🟡" if overall_score >= 60 else "🔴"
    
    report_lines.extend([
        f"{score_emoji} **Overall Performance Score: {overall_score:.1f}/100**",
        f"",
        f"---",
        f"",
        f"## 🎯 Reliability Metrics",
        f"",
        f"| Metric | Value | Target | Status |",
        f"|--------|-------|--------|--------|"
    ])
    
    for metric_name, metric_data in reliability.items():
        value = metric_data['value']
        target = metric_data['target']
        
        # Determine status
        if '>= ' in target:
            target_val = float(target.split('>= ')[1].replace('%', ''))
            status = "✅" if value >= target_val else "❌"
        elif '<= ' in target:
            target_val = float(target.split('<= ')[1].replace('%', '').replace(' ', ''))
            status = "✅" if value <= target_val else "❌"
        else:
            status = "❓"
        
        unit = "%" if "rate" in metric_name else ""
        report_lines.append(
            f"| {metric_name.replace('_', ' ').title()} | {value:.1f}{unit} | {target} | {status} |"
        )
    
    report_lines.extend([
        f"",
        f"## ⚡ Efficiency Metrics",
        f"",
        f"| Metric | Value | Target | Status |",
        f"|--------|-------|--------|--------|"
    ])
    
    for metric_name, metric_data in efficiency.items():
        value = metric_data['value']
        target = metric_data.get('target', 'N/A')
        unit = metric_data.get('unit', '')
        
        # Determine status based on target
        if target != 'N/A':
            if ' - ' in target:  # Range
                low, high = map(float, target.split(' - '))
                status = "✅" if low <= value <= high else "❌"
            elif target.startswith('<'):
                target_val = float(target.lstrip('< ').replace(',', ''))
                status = "✅" if value < target_val else "❌"
            else:
                status = "❓"
        else:
            status = "➖"
        
        report_lines.append(
            f"| {metric_name.replace('_', ' ').title()} | {value:.1f} {unit} | {target} | {status} |"
        )
    
    report_lines.extend([
        f"",
        f"## 🔬 Quality Metrics",
        f"",
        f"| Metric | Value | Target | Status |",
        f"|--------|-------|--------|--------|"
    ])
    
    for metric_name, metric_data in quality.items():
        value = metric_data['value']
        target = metric_data.get('target', 'N/A')
        unit = metric_data.get('unit', '')
        
        # Determine status
        if target != 'N/A':
            if target.startswith('>='):
                target_val = float(target.lstrip('>= ').replace('%', ''))
                status = "✅" if value >= target_val else "❌"
            elif target == '0':
                status = "✅" if value == 0 else "❌"
            elif target == '100%':
                status = "✅" if value == 100 else "❌"
            else:
                status = "❓"
        else:
            status = "➖"
        
        report_lines.append(
            f"| {metric_name.replace('_', ' ').title()} | {value:.1f} {unit} | {target} | {status} |"
        )
    
    # Add insights section
    report_lines.extend([
        f"",
        f"## 💡 Insights",
        f""
    ])
    
    insights = []
    
    if reliability.get('task_completion_rate', {}).get('value', 0) < 90:
        insights.append("⚠️ Task completion rate below target. Consider reviewing blocked features.")
    
    if reliability.get('regression_rate', {}).get('value', 0) > 5:
        insights.append("⚠️ High regression rate detected. Strengthen regression check protocol.")
    
    if quality.get('average_test_coverage', {}).get('value', 0) < 70:
        insights.append("⚠️ Test coverage below target. Encourage test-first development.")
    
    if efficiency.get('estimation_accuracy', {}).get('value', 0) < 0.8:
        insights.append("📊 Features taking longer than estimated. Review complexity assessments.")
    
    if insights:
        report_lines.extend(insights)
    else:
        report_lines.append("✅ All metrics within target ranges. Great performance!")
    
    # Add project stats
    if feature_list:
        total = len(feature_list)
        completed = len([f for f in feature_list if f.get('passes', False)])
        pending = len([f for f in feature_list if f.get('status') == 'pending'])
        in_progress = len([f for f in feature_list if f.get('status') == 'in_progress'])
        
        report_lines.extend([
            f"",
            f"## 📈 Project Progress",
            f"",
            f"- **Total Features**: {total}",
            f"- **Completed**: {completed} ({completed/total*100:.1f}%)",
            f"- **In Progress**: {in_progress}",
            f"- **Pending**: {pending}",
            f"",
            f"**Progress Bar**: {'█' * int(completed/total*20)}{'░' * (20 - int(completed/total*20))} {completed/total*100:.1f}%",
            f""
        ])
    
    # Write report
    output_file.parent.mkdir(parents=True, exist_ok=True)
    with open(output_file, 'w') as f:
        f.write('\n'.join(report_lines))
    
    print(f"Metrics report generated: {output_file}")


def main():
    parser = argparse.ArgumentParser(description="Generate ADDS performance metrics")
    parser.add_argument(
        '--project-dir',
        type=Path,
        default=Path.cwd(),
        help='Project directory (default: current directory)'
    )
    parser.add_argument(
        '--output',
        type=Path,
        help='Output report file (default: .ai/reports/metrics_YYYY-MM-DD.md)'
    )
    
    args = parser.parse_args()
    
    training_data_dir = args.project_dir / '.ai' / 'training_data'
    feature_file = args.project_dir / '.ai' / 'feature_list.json'
    
    # Load data
    feature_list = load_feature_list(args.project_dir)
    performance_data = load_performance_data(training_data_dir)
    
    # Calculate metrics
    reliability = calculate_reliability_metrics(feature_list, performance_data)
    efficiency = calculate_efficiency_metrics(performance_data)
    quality = calculate_quality_metrics(feature_list, performance_data)
    
    # Determine output file
    if args.output:
        output_file = args.output
    else:
        reports_dir = args.project_dir / '.ai' / 'reports'
        date_str = datetime.now().strftime('%Y-%m-%d')
        output_file = reports_dir / f'metrics_{date_str}.md'
    
    # Generate report
    generate_metrics_report(reliability, efficiency, quality, output_file, args.project_dir)
    
    # Print summary
    print("\n" + "="*60)
    print("PERFORMANCE METRICS SUMMARY")
    print("="*60)
    if reliability:
        print(f"Task Completion Rate: {reliability['task_completion_rate']['value']:.1f}%")
    if efficiency:
        print(f"Estimation Accuracy: {efficiency['estimation_accuracy']['value']:.2f}")
    if quality:
        print(f"Average Test Coverage: {quality['average_test_coverage']['value']:.1f}%")
    print("="*60)


if __name__ == '__main__':
    main()
