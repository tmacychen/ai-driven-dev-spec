# Changelog

All notable changes to the AI-Driven Development Specification (ADDS) project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [3.0.0] - 2026-03-10

### Added ⭐

**Reference**: [Anthropic - Effective Harnesses for Long-Running Agents](https://www.anthropic.com/engineering/effective-harnesses-for-long-running-agents)

Inspired by Anthropic's research on harness engineering for long-running agents, which addresses the core challenge of multi-session agent development.

- **Cross-Platform Installer**
  - Unified Python script (init-adds.py) for Windows/Linux/macOS
  - Interactive prompts for existing project handling
  - Dry-run mode for safe preview

### Changed - Anthropic Pattern Alignment

- **Environment Health Check** ⭐ CRITICAL
  - Mandatory pre-feature validation
  - "Start the session by running a basic test on the development server to catch any undocumented bugs"
  - Fix-first policy: environment issues must be resolved before feature work

- **Regression Check** ⭐ CRITICAL
  - Enhanced from 1-2 features to 2-3 core features
  - "Every session must verify the system hasn't regressed before starting new work"
  - STOP policy: regression must be fixed before new features

- **Feature Count Requirement**
  - Emphasized 50-200 discrete features requirement
  - Prevents "one-shot" tendency where agent tries to complete everything at once

- **E2E Testing Guidance**
  - Added Puppeteer/Playwright recommendations
  - "Providing Claude with these kinds of testing tools dramatically improved performance"

### Removed - Project Simplification

- **Deleted Redundant Files**:
  - `workflows/` directory (merged to docs/)
  - `templates/scaffold/.ai/harness.md`
  - `templates/scaffold/.ai/training_data/` directory
  - `templates/scaffold/init.sh` (now dynamically generated)
  - `templates/scaffold/.gitignore` (now dynamically generated)
  - `scripts/analyze_failures.py`
  - `scripts/extract_ki.py`
  - `scripts/generate_metrics.py`
  - `scripts/init-adds.sh` (replaced by Python)
  - `scripts/init-adds.ps1` (replaced by Python)
  - `docs/quick-reference.md` (duplicate)
  - `docs/workflow-example.md` (duplicate)

### Internationalization

- All documentation converted to English
- Consistent English terminology for AI Agent consumption

---

## [2.2.0] - 2026-03-04

### Added - Middleware Pattern Implementation ⭐

**Reference**: [LangChain Blog - Improving Deep Agents with Harness Engineering](https://blog.langchain.com/improving-deep-agents-with-harness-engineering/)

Inspired by LangChain's approach to harness engineering, which improved their coding agent from Top 30 to Top 5 on Terminal Bench 2.0.

- **Pre-Completion Checklist Middleware**
  - Mandatory exit gate before ending any session
  - Blocks session termination until all checks pass
  - Similar to "Ralph Wiggum Loop" pattern
  - Categories: Evidence Verification, Code Quality, State Persistence, Environment Health
  - Prevents premature session termination without proper verification

- **Auto Context Injection Middleware**
  - Directory Context: Auto-inject current directory structure
  - Tool Context: Auto-detect available tools (python, node, pytest, etc.)
  - Failure Pattern Context: Auto-inject recent failure patterns from training data
  - Context Summary: Generate structured context summary before starting work
  - Deterministic context injection helps agents verify their work

### Changed - Enhanced Session Flow

- **Feature Lifecycle**
  - Added `testing` status between `in_progress` and `completed`
  - Developer hands off to Tester after implementation
  - Tester verifies before marking as `completed`

---

## [2.3.0] - 2026-03-07

### Added

- **Multi-Agent Team Model**
  - Project Manager Agent (pm_prompt.md) — Requirement analysis and task decomposition
  - Architect Agent (architect_prompt.md) — Technical design and architecture
  - Developer Agent (developer_prompt.md) — Feature implementation
  - Tester Agent (tester_prompt.md) — Test verification and quality assurance
  - Reviewer Agent (reviewer_prompt.md) — Code review and security audit

- **Comprehensive Developer Prompt** (developer_prompt.md)
  - Full onboarding and environment check procedures
  - Loop detection and error recovery protocol
  - Pre-completion checklist as mandatory exit gate
  - Absolute prohibitions with violation consequences

### Changed

- **Initializer Prompt** split into PM + Architect roles
- **Coding Prompt** renamed to Developer Prompt with expanded scope

### Removed

- Two-phase agent pattern (Initializer + Coding) replaced by five-agent model

---

## [3.0.1] - 2026-03-24

### Fixed

- **License consistency**: README now correctly states GPL v3 (was mistakenly listed as MIT)
- **Version alignment**: ADDS_VERSION in init-adds.py updated from "2.3" to "3.0.0" to match CHANGELOG

### Changed

- **Prompt cleanup**: Removed legacy v2.x prompt files that were superseded by v3.0 multi-agent prompts:
  - `coding_prompt.md` (replaced by `developer_prompt.md`)
  - `review_prompt.md` (replaced by `reviewer_prompt.md`)
  - `testing_prompt.md` (replaced by `tester_prompt.md`)
- **Scaffold templates** updated to use v3.0 prompt set
- **.gitignore**: Added dynamic .gitignore generation to init-adds.py
- **README project structure**: Updated to reflect actual file layout
