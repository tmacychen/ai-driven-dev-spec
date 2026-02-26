# Training Data Directory

This directory collects learning data from Agent development sessions, enabling continuous improvement of the harness and future model training.

## Purpose

According to Phil Schmid's insight: **"Treat your Harness as a dataset"**

- Every failure is training data
- Every success pattern is a best practice
- Collected data feeds back into harness improvement and model training

## Directory Structure

```
training_data/
├── failures.jsonl           # Failed attempts and how they were resolved
├── successes.jsonl          # Successful patterns and efficiency metrics
├── performance.jsonl        # Per-feature performance metrics
├── context_metrics.jsonl    # Context window usage patterns
└── reports/                 # Weekly/monthly analysis reports
    ├── weekly_YYYY-MM-DD.md
    └── monthly_YYYY-MM.md
```

## Data Format

### failures.jsonl

Each line is a JSON object:

```json
{
  "feature_id": "F002",
  "failure_type": "test_failure",
  "timestamp": "2026-02-26T14:30:00Z",
  "session_id": "sess_abc123",
  
  "error_details": {
    "symptoms": "Login API returns 500 error",
    "root_cause": "Database connection not initialized",
    "stack_trace": "...",
    "affected_tests": ["test-002-01", "test-002-02"]
  },
  
  "recovery": {
    "retry_count": 2,
    "resolution": "Added DB health check to init.sh",
    "resolution_time_minutes": 15,
    "resolution_type": "environment_fix"
  },
  
  "context": {
    "previous_features": ["F001"],
    "model_version": "claude-3.5-sonnet",
    "session_length_minutes": 45,
    "context_window_usage": "78%",
    "time_in_session": "2/3"
  },
  
  "learning_value": {
    "pattern": "Missing environment validation",
    "category": "environment_setup",
    "generalizable": true,
    "severity": "medium",
    "suggested_prevention": "Add DB health check to init.sh template for all DB projects",
    "related_features": []
  }
}
```

### successes.jsonl

```json
{
  "feature_id": "F003",
  "timestamp": "2026-02-26T15:00:00Z",
  "session_id": "sess_def456",
  
  "success_factors": [
    "Clear test cases with explicit steps",
    "Small scope (single feature)",
    "Complete validation_requirements defined"
  ],
  
  "timing": {
    "estimated_minutes": 120,
    "actual_minutes": 90,
    "efficiency_ratio": 1.33
  },
  
  "tool_usage": {
    "test_runs": 3,
    "code_edits": 12,
    "git_commits": 1,
    "lines_added": 150,
    "lines_removed": 10
  },
  
  "quality_metrics": {
    "test_coverage": "85%",
    "lint_errors": 0,
    "type_errors": 0
  },
  
  "patterns": [
    {
      "pattern": "test_first_development",
      "effectiveness": "high"
    },
    {
      "pattern": "small_incremental_commits",
      "effectiveness": "high"
    }
  ]
}
```

### performance.jsonl

```json
{
  "feature_id": "F003",
  "timestamp": "2026-02-26T15:00:00Z",
  
  "reliability": {
    "completed": true,
    "retry_count": 0,
    "regression_introduced": false
  },
  
  "efficiency": {
    "time_minutes": 90,
    "estimated_minutes": 120,
    "efficiency_score": 1.33,
    "context_tokens_used": 45000
  },
  
  "quality": {
    "test_coverage": "85%",
    "lint_errors": 0,
    "documentation_complete": true
  }
}
```

## Privacy & Anonymization

The following data is automatically removed or hashed:
- Passwords, tokens, API keys
- User identifiers (hashed)
- File paths containing sensitive information
- Environment-specific configuration values

## Usage

### For Harness Improvement

1. **Analyze failures** → Identify common patterns
2. **Extract lessons** → Update best practices
3. **Optimize flows** → Reduce friction points

### For Model Training (Future)

1. **Export dataset** → Fine-tune models on project-specific patterns
2. **Improve persistence** → Enhance long-context performance
3. **Domain adaptation** → Specialize for software development

## Analysis Scripts

Located in `scripts/`:

- `analyze_failures.py` - Identify failure patterns
- `extract_patterns.py` - Find successful approaches
- `generate_report.py` - Create weekly/monthly summaries
- `export_training_data.py` - Prepare data for model training

## Contribution

Data is automatically collected during development sessions. To manually annotate:

1. Review generated reports in `reports/`
2. Add insights to `.ai/insights.md`
3. Suggest improvements via harness_config.json

---

**Remember**: This data is the long-term value of your Agent Harness. Every session contributes to making future development faster and more reliable.
