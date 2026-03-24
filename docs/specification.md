# AI-Driven Development Specification (ADDS) v3.0 Core Guide

> This guide defines a structured approach to help AI Agents continuously, stably, and safely advance projects across multiple context windows in long-cycle software development tasks.

---

## 1. Core Challenge: Context Fragmentation

The biggest problem facing long-running AI tasks is **context fragmentation**:
- **State Loss**: At the start of each new session, the Agent is "amnesiac".
- **Overreaching**: Agents tend to complete all features in one shot, leading to decreased code quality or context overflow.
- **Premature Completion**: Agents seeing existing code may mistakenly believe tasks are complete.
- **Environment Fragmentation**: Unconfigured environments or missing dependencies prevent new sessions from starting work immediately.
- **Regression Blind Spots**: New features break old ones, and Agents continue without noticing.
- **Security Out of Control**: Agents execute dangerous commands without any constraints.

---

## 2. Multi-Agent Team Model

> **LangChain Pattern**: "The purpose of the harness engineer: prepare and deliver context so agents can autonomously complete work."

We decompose tasks into specialized roles, each executed by a dedicated agent prompt:

### 2.1 Project Manager Agent
- **Responsibility**: Requirements analysis and task decomposition.
- **Trigger Condition**: Project first launch, or when `.ai/feature_list.md` file does not exist.
- **Tasks**:
    - Read original requirements (`app_spec.md` or `app_spec.txt`).
    - Break down feature list, generate `.ai/feature_list.md` (containing 50-200 atomic test cases).
    - Assign priorities and dependencies.
    - Track progress and manage scope.
- **Prompt File**: `.ai/prompts/pm_prompt.md`

### 2.2 Architect Agent
- **Responsibility**: Technical design and architecture.
- **Trigger Condition**: PM completes requirement analysis.
- **Tasks**:
    - Design system architecture.
    - Select technology stack.
    - Generate `.ai/architecture.md` to record technology selection and architecture decisions.
    - Write `init.sh` for automated environment configuration.
- **Prompt File**: `.ai/prompts/architect_prompt.md`

### 2.3 Developer Agent
- **Responsibility**: Feature implementation.
- **Trigger Condition**: Architecture approved, feature assigned.
- **Tasks**:
    - Implement ONE feature per session.
    - Write unit tests.
    - Self-verify implementation.
    - Update feature status to `testing`.
- **Prompt File**: `.ai/prompts/developer_prompt.md`

### 2.4 Tester Agent
- **Responsibility**: Test verification and quality assurance.
- **Trigger Condition**: Developer completes feature (status: `testing`).
- **Tasks**:
    - Run all test cases.
    - Verify acceptance criteria.
    - Run regression tests.
    - Document test results.
- **Prompt File**: `.ai/prompts/tester_prompt.md`

### 2.5 Reviewer Agent
- **Responsibility**: Code review and security audit.
- **Trigger Condition**: Tests pass.
- **Tasks**:
    - Review code quality.
    - Check security vulnerabilities.
    - Verify architecture compliance.
    - Approve or reject feature.
- **Prompt File**: `.ai/prompts/reviewer_prompt.md`

### 2.6 Agent Workflow

```
┌─────────────┐    ┌─────────────┐    ┌─────────────┐    ┌─────────────┐    ┌─────────────┐
│     PM      │───▶│  Architect  │───▶│  Developer  │───▶│   Tester    │───▶│  Reviewer   │
│             │    │             │    │             │    │             │    │             │
│ Requirements│    │ Architecture│    │ Feature     │    │ Test        │    │ Code Review │
│ Decomposition│    │ Design      │    │ Implementation│   │ Verification│   │ Security    │
└─────────────┘    └─────────────┘    └─────────────┘    └─────────────┘    └─────────────┘
```

### 2.7 Feature Lifecycle

```
pending → in_progress → testing → completed
                    ↓
                  bug → in_progress (fix)
```

---

## 3. Standard Project Skeleton (`.ai/` Directory)

Every project must contain the following "self-descriptive" files:

- **`.ai/feature_list.md`**: Single Source of Truth for features.
  Each feature must include:
  - `id`, `category`, `description`, `priority`, `core`
  - `status`, `dependencies`, `steps`, `test_cases`, `security_checks`
  - **`acceptance_criteria`**: Atomized completion checklist.
- **`progress.md`**: Human/Agent-oriented natural language progress summary.
  Uses incremental append mode, recording "completed", "in progress", "to-do items", and next handoff instructions.
- **`CORE_GUIDELINES.md`**: (New) Minimal self-boosting manual. Placed in project root directory for AI to instantly start and align development process.
- **`.ai/architecture.md`**: Records project architecture, technology stack selection, and core data flow.
- **`.ai/prompts/`**: Agent prompt files (pm, architect, developer, tester, reviewer).
- **`init.sh`**: Scripted environment. After running this script, any Agent should be able to immediately execute tests or start development.
- **`app_spec.md`**: Original project requirements source.

---

## 4. Incremental Development Process (SDLC for AI)

Every development session must follow these strict steps:

### 4.1 Environment Alignment (Align)
- Execute `pwd`, `ls` to familiarize with structure.
- Read `CORE_GUIDELINES.md` (quick start).
- Read `progress.md` and `.ai/feature_list.md`.
- Check `git log --oneline -10` to understand recent changes.

### 4.2 Environment Verification (Bootstrap) ⭐ CRITICAL

> **Anthropic Pattern**: "Start the session by running a basic test on the development server to catch any undocumented bugs. If the agent had instead started implementing a new feature, it would likely make the problem worse."

- Execute `init.sh` or run smoke tests to verify environment is healthy.
- Check if dependencies are installed (`node_modules/`, `venv/`, etc.).
- Check if services are running (`curl localhost:3000/health` etc.).
- **If anything fails: FIX IT FIRST before proceeding with any feature work.**
- This step is MANDATORY - do not skip even for small changes.

### 4.3 Regression Verification (Regression Check) ⭐ CRITICAL

> **Anthropic Pattern**: Every session must verify the system hasn't regressed before starting new work.

- Select 2-3 core features from completed features and run their tests.
- This prevents the "agent tends to try to do too much at once" problem.
- If existing features are broken:
  1. 🛑 **STOP** - Do NOT proceed with new feature development
  2. 🔧 **Prioritize fixing** regression issues BEFORE any new features
  3. Mark affected features as status: `regression` in `feature_list.md`
  4. 📝 **Record** in `progress.md`
  5. Re-run regression check until all pass
  6. Only then proceed to new features

### 4.4 Local Context Discovery ⭐ NEW (LangChain Pattern)

> **LangChain Pattern**: "Context discovery and search are error prone, so injecting context reduces this error surface and helps onboard the agent into its environment."

- **Directory Structure**: Map cwd, parent directories, key subdirectories
- **Available Tools**: Detect installed tools (python, node, npm, pytest, go, cargo, etc.)
- **Project Config**: Read package.json, requirements.txt, Cargo.toml, go.mod, etc.
- **Coding Standards**: Check for .eslintrc, .prettierrc, pyproject.toml, etc.
- **Test Framework**: Identify testing framework (jest, pytest, go test, etc.)

This context should be noted and used throughout the session to ensure compliance with project conventions.

### 4.5 Time Budget ⭐ NEW (LangChain Pattern)

> **LangChain Pattern**: "Agents are famously bad at time estimation so this heuristic helps. Time budgeting nudges the agent to finish work and shift to verification."

- Set a mental time budget for this session (e.g., 15-20 minutes per feature)
- If you approach the time limit:
  - Complete current atomic operation
  - Run validation tests
  - Prioritize committing work over perfect implementation
  - Leave clear handoff notes in `progress.md`

### 4.6 Task Selection (Select)
- Select the highest priority `pending` task from `feature_list.md`.
- Ensure all its `dependencies` are completed.
- Update status to `"status": "in_progress"`.

### 4.7 Implementation Execution (Execute)

> **LangChain Pattern**: "Forcing models to conform to testing standards is a powerful strategy to avoid 'slop buildup' over time."

- Write code. **Strictly prohibit** exceeding the scope of the currently selected task.
- Follow project coding standards, add necessary comments.
- Write corresponding test cases.
- **Write Testable Code**:
  - Follow exact file paths as specified in acceptance criteria
  - Test both happy paths AND edge cases
  - Write assertions that match automated scoring
  - Consider boundary conditions: empty inputs, max values, error states

### 4.8 Quality Assurance (QA)

> **LangChain Pattern**: "Verify: Run tests, read the FULL output, compare against what was asked (not against your own code)."

- Use tools (such as simulators, browsers, unit tests) to verify functionality.
- **Evidence-driven**: Agent **must** provide tool execution evidence.
- Only when all `test_cases` status are `passed` and `acceptance_criteria` are met can it be marked as complete.
- Choose verification method based on project type (see Section 5 for details).

### 4.9 Loop Detection ⭐ NEW (LangChain Pattern)

> **LangChain Pattern**: "Agents can be myopic once they've decided on a plan which results in 'doom loops' that make small variations to the same broken approach (10+ times in some traces)."

- Monitor your work during implementation
- If you've edited the same file 5+ times without success:
  - 🛑 **STOP** and reconsider your approach
  - Document what you've tried in `progress.md`
  - Ask for help or try a completely different strategy
  - Consider if the task is blocked by a dependency

### 4.10 Persistence (Persist)
- Execute `git add` / `git commit` with detailed commit messages.
- Update status in `feature_list.md`.
- Leave handoff instructions for "next developer" in `progress.md`.

---

## 5. Testing and Verification Standards

### 5.1 General Rules
- **Atomic Testing**: Each feature point must be independently testable.
- **Evidence-driven**: All features must provide tool execution results (logs, assertion outputs, screenshots) as completion evidence.
- **Test Case Embedding**: Each feature must include `test_cases` field in `feature_list.md`.

### 5.2 Web Projects (E2E Priority)
- Must use tools like Playwright/Cypress for end-to-end simulation.
- Simulate real user operations (clicks, inputs, scrolling).
- Verify page transitions, error message display, UI rendering.
- **Prohibit** using API calls to bypass UI verification.

### 5.3 API Projects
- Verify response status codes, data formats, error handling.
- Verify database status is correct.
- Use pytest / Newman and other tools for automated testing.

### 5.4 CLI Projects
- Test command line input/output.
- Verify exit codes are correct.
- Test exception parameter handling.

---

## 6. Secure Execution Specifications ⭐ New

### 6.1 Command Whitelist

AI **must** verify safety before executing any command.

#### ✅ Allowed Commands

| Category | Commands |
| :--- | :--- |
| **File Operations** | `ls`, `cat`, `head`, `tail`, `wc`, `grep`, `find`, `cp`, `mv` |
| **Node.js** | `npm`, `node`, `npx`, `yarn` |
| **Python** | `pip`, `python`, `pytest`, `black`, `flake8`, `mypy` |
| **Go** | `go`, `gofmt` |
| **Rust** | `cargo`, `rustc`, `rustfmt` |
| **Version Control** | `git` (all subcommands) |
| **Process Management** | `ps`, `lsof`, `sleep` |

#### ❌ Prohibited Commands

| Category | Commands | Reason |
| :--- | :--- | :--- |
| **Privilege Escalation** | `sudo`, `su` | System-level risk |
| **Permissions** | `chmod`, `chown` (unless explicitly necessary) | Permission changes |
| **Destructive** | `rm -rf /`, `mkfs`, `fdisk` | Irrecoverable data |
| **Network Backdoors** | `nc`, `netcat`, `telnet` | Security risks |
| **Firewall** | `iptables`, `route` | Network configuration changes |
| **Blind Downloads** | `curl \| bash`, `wget \| sh` | Unreviewed scripts |
| **System Process Killing** | `kill -9` (system processes) | System stability |

### 6.2 Pre-Execution Checklist

Each command execution must verify:

1. ✅ Is the command in the whitelist?
2. ✅ Are the parameters safe?
3. ✅ Does it not affect system files?
4. ✅ Are irreversible operations backed up?
5. ✅ If in doubt, ask the user first.

---

## 7. Feature Management and Locking ⭐ New

### 7.1 Core Features (core: true)
- ❌ **Cannot be deleted**
- ⚠️ Modifications require clear justification and change reasons must be recorded
- ✅ Can adjust priority

### 7.2 Extended Features (core: false)
- ✅ Can be deleted (must record reason)
- ✅ Can modify description/steps
- ✅ Can be postponed

### 7.3 Requirement Change Process
1. Update `app_spec.md` to reflect new requirements.
2. Evaluate impact on existing features.
3. Update `feature_list.md` (add/modify/postpone).
4. Record change reasons in `progress.md`.

---

## 8. Special Case Handling

### 8.1 Regression Issues (Regression)
```json
{
  "id": "F005",
  "status": "regression",
  "regression_details": {
    "detected_at": "2026-02-26T14:00:00Z",
    "symptoms": "Login functionality returns 500 error",
    "likely_cause": "F010's database migration broke the user table",
    "affected_tests": ["test-005-01"]
  }
}
```
- Prioritize fixing regression issues before continuing with new features.

### 8.2 Blocking Issues (Blocked)
- Update feature status to `"status": "blocked"`, record `blocked_reason`.
- Skip the feature, select next executable feature.
- Record blocking details in `progress.md`.

### 8.3 Project Interruption Recovery
1. Read `progress.md` to understand history.
2. Read `.ai/feature_list.md` to check current status.
3. Execute `git log` to see recent commits.
4. Run environment verification and regression tests.
5. Continue with next pending feature.

### 8.4 Standardized Error Recovery (Retry & Escalation) ⭐ New
When an Agent encounters execution errors or test failures, it should follow this protocol:
1. **Automatic Classification**: Determine if it's an environment issue (run `init.sh`), code issue (auto-fix), or requirement issue (consult documentation).
2. **Retry Count**: Track retry attempts in `feature_list.md`.
3. **Backoff and Rollback**: If `max_retries` is reached, Agent must:
   - Execute `git reset --hard` to last stable state.
   - Mark status as `"blocked"`.
   - Record specific `blocked_reason`.
   - Skip the task, try next task in queue.
   - Record the decision in `progress.md`.

---

## 9. Git Commit Standards

- Each feature completion **must** be committed.
- **Strictly prohibit** committing multiple features at once.
- Commit message format:

```
<type>(<scope>): <description> [Closes #feature-id]

- Implementation detail 1
- Implementation detail 2
- Add test cases
```

**Type Categories**:
- `feat:` New feature
- `fix:` Bug fix
- `refactor:` Code refactoring
- `test:` Test related
- `docs:` Documentation update
- `chore:` Build/tool related

---

## 10. Project Completion Standards

| Dimension | Requirement |
| :--- | :--- |
| **Feature Completion** | All features `completed`, no `blocked` or `regression` |
| **Test Coverage** | Test coverage ≥ 70% |
| **Code Quality** | No lint errors, passes type checking |
| **Documentation** | Complete README, clear API documentation, sufficient code comments |
| **Git History** | One commit per feature, clear messages, no redundancy |

---

## 11. Best Practices

### Feature Splitting
- **Moderate Granularity**: One feature completed in 1-4 hours
- **Independent Testability**: No dependencies on unfinished features
- **Clear Value**: Each feature has clear business value
- **Clear Boundaries**: Distinct responsibilities between features

### Code Quality
- **Test-Driven**: Write tests first, then implementation
- **Continuous Refactoring**: Keep code clean
- **Documentation Synchronization**: Code and documentation remain consistent
- **Version Control**: Small, frequent commits

### State Management
- **Timely Updates**: Update status immediately after completing features.
- **Humanized Logs**: Incrementally record each session's decisions and achievements in `progress.md`.
- **Regular Review**: Check progress and remaining work

---

## 12. Context Management and Learning

### 12.1 Core Concept

Long-running projects generate increasingly large context files. Without management, `progress.md` can grow to thousands of lines, consuming valuable context window space and degrading Agent performance.

Key principles:
- **Compress, don't lose**: Historical data should be summarized, not deleted
- **Recent context is king**: The last few sessions contain the most actionable information
- **Patterns emerge from data**: Failed features and blocked tasks contain valuable lessons

### 12.2 Context Compression

Use the built-in `scripts/compress_context.py` tool to manage `progress.md` growth:

```bash
# Check if compression is needed (threshold: 1000 lines by default)
python scripts/compress_context.py --project-dir /path/to/project

# Force compression regardless of threshold
python scripts/compress_context.py --project-dir /path/to/project --force

# Keep more recent sessions (default: 10)
python scripts/compress_context.py --keep-recent 20
```

The tool:
1. Archives the original `progress.md` as `progress.md.archive`
2. Keeps the most recent N sessions in full detail
3. Generates `progress_summary.md` with statistics and historical overview
4. Reports compression ratio

### 12.3 When to Compress

- When `progress.md` exceeds ~1000 lines
- At the start of a new milestone or phase
- Before onboarding a new team member or Agent session

### 12.4 Lessons Learned

Record failure patterns and recovery strategies directly in `progress.md`:

```markdown
## [YYYY-MM-DD HH:MM] Session: Developer Agent

### Lessons Learned
- **Issue**: Database connection timeout during E2E tests
- **Root Cause**: Connection pool not configured for test environment
- **Prevention**: Added health check to init.sh
- **Feature**: F015 - Payment Processing
```

---

## 13. Module Evolution Strategy

### 13.1 "Built for Deletion" Principle

Core concept: Anticipating that new models will replace current logic, the architecture must be modular and ready to "rip out" old code at any time. ADDS is designed as a set of independent prompt files and guidelines that can be individually updated or replaced.

### 13.2 Module Examples

Current modules that may evolve as AI capabilities improve:

| Module | Current Status | Likely Future |
|--------|---------------|---------------|
| Multi-Agent separation | Enabled (models need role specialization) | May consolidate as models improve |
| Regression check | Enabled (models still introduce regressions) | Keep until models self-verify |
| Command whitelist | Enabled (security constraint) | May relax for sandboxed environments |
| Loop detection | Enabled (models still fall into doom loops) | May reduce as models improve |

### 13.3 Evolution Approach

To update ADDS modules:
1. Update the relevant prompt file in `.ai/prompts/`
2. Update `CORE_GUIDELINES.md` to reflect the change
3. Run `init-adds.py --upgrade` (see upgrade mechanism) to propagate changes
4. Document the change in CHANGELOG

---

## 14. Performance Evaluation Metrics ⭐ New

### 14.1 Reliability Metrics

| Metric | Definition | Target |
|------|------|------|
| **Task Completion Rate** | Successfully completed features / total features | ≥ 90% |
| **Regression Rate** | Introduced regression issues / completed features | ≤ 5% |
| **Blocking Rate** | Blocked features / total features | ≤ 10% |
| **Retry Rate** | Features requiring retries / total features | ≤ 50% |

### 14.2 Efficiency Metrics

| Metric | Definition | Target |
|------|------|------|
| **Average Development Time** | Actual time per feature | As estimated |
| **Estimation Accuracy** | Actual time / estimated time | 0.8 - 1.2 |
| **Context Utilization** | Effective operations / total token usage | Optimizing |

### 14.3 Quality Metrics

| Metric | Definition | Target |
|------|------|------|
| **Test Coverage** | Test code lines / total code lines | ≥ 70% |
| **Code Quality** | Number of lint errors, type errors | 0 |
| **Documentation Completeness** | Documented features / total features | 100% |

### 14.4 System-Level Evaluation

**Long-term Stability**:
- **Context Persistence**: Cross-session state retention accuracy
- **Environment Consistency**: init.sh success rate
- **Recovery Capability**: Success rate of automatic recovery from errors

### 14.5 Evaluation Reports

Use `scripts/compress_context.py` to generate progress summaries, or manually review `progress.md` for session-by-session details.

Reports should include:
- Overall performance score
- Reliability metrics (completion rate, regression rate)
- Efficiency metrics (time per feature)
- Quality metrics (test coverage, lint errors)
- Improvement suggestions

---

## 📚 Getting Started

1. **Check Project Status** — See if `.ai/feature_list.md` already exists
2. **Determine Current Agent** — Use the Agent Selection Logic (see CORE_GUIDELINES.md)
3. **Follow the Process** — Strictly follow the above specifications

**Remember**: Your goal is to complete project development with high quality, sustainability, and safety. Follow the specifications, reduce mistakes, and ensure each feature is fully verified.

**Let's start!** 🚀