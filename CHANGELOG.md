# Changelog

All notable changes to the AI-Driven Development Specification (ADDS) project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [2.1.0] - 2026-02-26

### Added - Data Collection Infrastructure ⭐

**Core Value Proposition**: Treat Harness as a Dataset (Phil Schmid's insight)

- **Data Collection Configuration**
  - `.ai/data_collection_config.json`: Configure what data to collect
  - Automated collection of failures, successes, timing, and context usage
  - Privacy-aware anonymization of sensitive data

- **Training Data Directory Structure**
  - `.ai/training_data/failures.jsonl`: Failed attempts and resolutions
  - `.ai/training_data/successes.jsonl`: Success patterns and efficiency metrics
  - `.ai/training_data/performance.jsonl`: Per-feature performance metrics
  - `.ai/training_data/context_metrics.jsonl`: Context window usage patterns
  - `.ai/training_data/README.md`: Documentation for data usage

- **Analysis Tools**
  - `scripts/analyze_failures.py`: Identify common failure patterns and generate recommendations
  - `scripts/generate_metrics.py`: Generate comprehensive performance reports

### Added - Modular Harness Configuration ⭐

**"Build for Deletion" Philosophy**: Anticipate that new models will obsolete current logic

- **Harness Configuration**
  - `.ai/harness_config.json`: Modular configuration with enable/disable flags
  - Document rationale for each module
  - Set review dates for re-evaluation
  - Define alternatives for future models

- **Supported Modules**
  - dual_agent_pattern: Role separation for initialization vs. coding
  - regression_check: Prevent breaking existing features
  - atomic_commits: Single feature per session
  - environment_validation: Ensure environment consistency
  - tool_based_validation: Require evidence for completion
  - command_whitelist: Security guardrails
  - data_collection: Learning value capture

### Added - Performance Metrics System ⭐

- **Reliability Metrics**
  - Task completion rate (target: ≥ 90%)
  - Regression rate (target: ≤ 5%)
  - Blocked rate (target: ≤ 10%)
  - Retry rate (target: ≤ 0.5)

- **Efficiency Metrics**
  - Average development time
  - Estimation accuracy (target: 0.8 - 1.2 ratio)
  - Context window utilization

- **Quality Metrics**
  - Test coverage (target: ≥ 70%)
  - Lint errors (target: 0)
  - Documentation completeness (target: 100%)

- **System-Level Evaluation**
  - Context persistence across sessions
  - Environment consistency
  - Auto-recovery success rate

### Changed - Enhanced Constraints

- **Absolute Prohibitions Section** in `coding_prompt.md`
  - Added 6 strictly forbidden behaviors with examples and detection mechanisms
  - Defined violation consequences (revert, record, mark blocked)

- **Error Recovery Protocol** in `coding_prompt.md`
  - Added automatic error classification (environment/dependency/code/requirements/capability)
  - Defined recovery procedures for each error type
  - Established autonomous decision principles

- **Validation Requirements** in `feature_list.json`
  - Added `validation_requirements` field with specific evidence types
  - Added `completion_criteria` for unambiguous completion definition
  - Added `retry_count`, `max_retries`, `escalation` for error recovery

### Changed - Documentation Updates

- Updated `initializer_prompt.md` to require data collection infrastructure setup
- Updated `coding_prompt.md` to require data collection on each session
- Updated `specification.md` with new chapters:
  - Chapter 12: Data Collection & Learning Mechanism
  - Chapter 13: Harness Modular Configuration
  - Chapter 14: Performance Evaluation Metrics
- Updated `README.md` to reflect v2.1 features

### Influences

This release is heavily influenced by:

1. **Phil Schmid's Article**: "The importance of Agent Harness in 2026"
   - Concept: Harness as OS for AI agents
   - Key insight: Treat harness as dataset
   - Principle: Build for deletion

2. **Anthropic's Best Practices**: From the critical review document
   - Stronger constraints rather than more tools
   - Clear validation standards
   - Autonomous error recovery

### Breaking Changes

None. All changes are additive and backward compatible.

### Migration Guide

For existing ADDS v2.0 projects:

1. Add `.ai/data_collection_config.json` (copy from `templates/scaffold/.ai/`)
2. Add `.ai/harness_config.json` (copy from `templates/scaffold/.ai/`)
3. Create `.ai/training_data/` directory
4. Update `.gitignore` to exclude `.ai/training_data/*.jsonl`
5. Optional: Run `python scripts/generate_metrics.py` to establish baseline metrics

---

## [2.0.0] - 2026-02-20

### Added

- Dual-agent pattern (Initializer + Coding Agent)
- Feature list with test cases and acceptance criteria
- Security command whitelist
- Environment health checks with init.sh
- Regression detection mechanism
- Core feature locking
- Browser automation support (E2E)
- Session stability verification
- Multi-language support (Node.js, Python, Go, Rust)
- Detailed testing prompt
- Code review checklist

### Changed

- Improved documentation structure
- Enhanced state management files

---

## [1.0.0] - 2025-12-01

### Added

- Initial release
- Basic feature list tracking
- Progress logging
- Git integration
- Simple environment validation
