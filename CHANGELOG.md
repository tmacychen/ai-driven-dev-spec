# Changelog

All notable changes to the AI-Driven Development Specification (ADDS) project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Added ⭐

- **P1 功能 10: 技能渐进式披露** — Level 0/1/2 三级技能加载
  - `skill_manager.py`: SkillManager 管理器（注册/加载/匹配/统计/持久化）
  - Level 0: 技能列表索引（~50 token/skill），始终注入 System Prompt
  - Level 1: 技能详情（~200-500 token/skill），按需加载
  - Level 2: 技能参考文件（~500-2000 token/skill），执行时加载
  - 关键词匹配与推荐 (`match_skills`/`suggest_skills`)
  - 从 SkillGenerator 导入技能
  - `adds skill` CLI 子命令（list/view/load/match/register/import/delete/stats）
  - AgentLoop `/skill` 命令集成
  - System Prompt Level 0/Level 1 自动注入

- **P1 功能 11: Agent Loop 韧性增强** — 循环状态机与恢复策略
  - `loop_state.py`: LoopStateMachine 7种终止+5种继续+5类错误分类
  - `_call_model_with_resilience()`: max_output_tokens续写+PTL恢复+错误重试
  - 指数退避策略 + 用户中止检测

- **Bug Fix: index.mem 自动索引更新机制**
  - `MemoryManager._upgrade_memory_sync()` 自动写入索引条目
  - 新增 `MemoryManager.add_item()` 方法
  - 新增 `adds mem add` 子命令
  - `adds.py` 添加 `mem_command()` handler

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

## [Unreleased]

### Added - P1: Agent Loop Resilience ⭐

- **LoopStateMachine** (`scripts/loop_state.py`)
  - 7 termination conditions: completed, blocking_limit, aborted_streaming, model_error, prompt_too_long, image_error, hook_prevented
  - 5 continue conditions: normal, max_output_tokens, prompt_too_long, error_retry, hook_retry
  - Error classification: environment, model, user_abort, system, unknown
  - Exponential backoff with jitter (configurable base/max)
  - ResilienceConfig for all retry/timeout/threshold parameters

- **Agent Loop Resilience Integration** (`scripts/agent_loop.py`)
  - `_call_model_with_resilience()`: resilient model call with retry/continuation/PTL recovery
  - `_try_compact_for_ptl()`: PTL recovery via Layer1 compact + Layer2 archive
  - max_output_tokens continuation: detects `length` truncation → continuation prompt (max 3 retries)
  - PTL recovery: detects 413/context_length → compress context → retry (max 2 retries)
  - Environment error retry: ConnectionError/TimeoutError → exponential backoff (max 2 retries)
  - User abort detection: KeyboardInterrupt → graceful termination

- **P1 Resilience Tests** (`scripts/test_p1_resilience.py`)
  - 10 test scenario classes covering all termination/continue/error/backoff cases

---

## [3.0.1] - 2026-03-24

### Added

- **`setup.py` — Unified installer** at project root
  - Installs tool scripts to `<prefix>/bin/` (default `/usr/local/bin`) by copying and setting `chmod +x`
  - Command names derived automatically from script filenames (e.g. `adds.py` → `adds`)
  - `INSTALL_SCRIPTS` list in the file header defines exactly which scripts are installed per release
  - `REMOVED_SCRIPTS` list for cleanup of commands dropped in a given version
  - `--upgrade`: removes obsolete commands (with confirmation), then force-installs current version
  - `--uninstall`: shows full paths of files to delete, requires `y/N` confirmation; if a file is not found in the default directory, prints command name and `which <cmd>` instructions for manual removal
  - `--check`: read-only status view (installed, up-to-date, PATH check)
  - `--dry-run`: previews all operations without modifying any files
  - `--prefix <dir>`: install to any directory (e.g. `~/.local` for user-only installs)

### Fixed

- **License consistency**: README now correctly states GPL v3 (was mistakenly listed as MIT)
- **Version alignment**: ADDS_VERSION in init-adds.py updated from "2.3" to "3.0.0" to match CHANGELOG

### Changed

- **README**: CLI installation section updated to use `setup.py` instead of manual `chmod + ln -s`
- **README**: Upgrade and uninstall sections rewritten to reflect `setup.py` workflow
- **Script permissions**: All scripts under `scripts/` set to executable (`chmod +x`)
- **Prompt cleanup**: Removed legacy v2.x prompt files that were superseded by v3.0 multi-agent prompts:
  - `coding_prompt.md` (replaced by `developer_prompt.md`)
  - `review_prompt.md` (replaced by `reviewer_prompt.md`)
  - `testing_prompt.md` (replaced by `tester_prompt.md`)
- **Scaffold templates** updated to use v3.0 prompt set
- **.gitignore**: Added dynamic .gitignore generation to init-adds.py
- **README project structure**: Updated to reflect actual file layout
