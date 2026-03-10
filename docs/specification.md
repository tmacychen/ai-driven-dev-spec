# AI-Driven Development Specification (ADDS) v2.0 Core Guide

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

## 2. Dual Agent Role Model

We decompose tasks into two core phases, executed by two different prompts (or Agents):

### 2.1 Initializer Agent
- **Responsibility**: Project startup.
- **Trigger Condition**: Project first launch, or when `.ai/feature_list.md` file does not exist.
- **Tasks**:
    - Read original requirements (`app_spec.md` or `app_spec.txt`).
    - Break down feature list, generate `.ai/feature_list.md` (containing 50-200 atomic test cases).
    - Set up basic directory structure.
    - Generate `.ai/architecture.md` to record technology selection and architecture decisions.
    - Write `init.sh` for automated environment configuration.
    - Submit initial Git Commit.

### 2.2 Coding Agent
- **Responsibility**: Incremental iteration.
- **Trigger Condition**: All subsequent sessions.
- **Tasks**:
    - Read progress files (`progress.log`) and feature list.
    - **Execute environment verification** (run `init.sh` or smoke tests).
    - **Run regression tests for 1-2 core features**.
    - Run tests to determine current status.
    - **Select only one** feature for development at a time.
    - Complete development, self-test, Git commit, and update progress.

---

## 3. Standard Project Skeleton (`.ai/` Directory)

Every project must contain the following "self-descriptive" files:

- **`.ai/feature_list.md`**: Single Source of Truth for features.
  Each feature must include:
  - `id`, `category`, `description`, `priority`, `core`
  - `status`, `dependencies`, `steps`, `test_cases`, `security_checks`
  - **`acceptance_criteria`**: Atomized completion checklist.
- **`progress.log`**: Human/Agent-oriented natural language progress summary.
  Uses incremental append mode, recording "completed", "in progress", "to-do items", and next handoff instructions.
- **`CORE_GUIDELINES.md`**: (New) Minimal self-boosting manual. Placed in project root directory for AI to instantly start and align development process.
- **`.ai/architecture.md`**: Records project architecture, technology stack selection, and core data flow.
- **`.ai/session_log.jsonl`**: Machine-readable session history (one JSON object per line).
- **`init.sh`**: Scripted environment. After running this script, any Agent should be able to immediately execute tests or start development.
- **`.ai/harness.md`**: Harness modular configuration, supporting the "built for deletion" philosophy.
- **`.ai/training_data/` (New ⭐)**: Training data directory, storing failure cases, success patterns, and performance metrics.
  - `failures.jsonl`: Failure cases and solutions
  - `successes.jsonl`: Success patterns and efficiency metrics
  - `performance.jsonl`: Performance metrics data
  - `context_metrics.jsonl`: Context usage patterns
- **`docs/KNOWLEDGE_ITEMS/` (New ⭐)**: Knowledge base automatically generated from failure data, recording verified solutions.

---

## 4. Incremental Development Process (SDLC for AI)

Every development session must follow these strict steps:

### 4.1 Environment Alignment (Align)
- Execute `pwd`, `ls` to familiarize with structure.
- Read `CORE_GUIDELINES.md` (quick start).
- Read `progress.log` and `.ai/feature_list.md`.
- Check `git log --oneline -10` to understand recent changes.

### 4.2 Environment Verification (Bootstrap)
- Execute `init.sh` or existing tests to ensure Agent takes over a normal project.
- Check if dependencies are installed (`node_modules/`, `venv/`, etc.).
- Check if services are running (`curl localhost:3000/health` etc.).
- **Execute deep health check**: Verify all deep assertions defined in `harness.md` (database, API, etc.).
- If problems are found, **fix first before continuing**.

### 4.3 Regression Verification (Regression Check) ⭐ New
- Select 1-2 core features from completed features and run their tests.
- If existing features are broken:
  1. 🛑 **Immediately stop** new feature development.
  2. 🔧 **Prioritize fixing** regression issues.
  3. Mark affected features as status: `regression` in `feature_list.md`.
  4. 📝 **Record** in `progress.log`.

### 4.4 Task Selection (Select)
- Select the highest priority `pending` task from `feature_list.md`.
- Ensure all its `dependencies` are completed.
- Update status to `"status": "in_progress"`.

### 4.5 Implementation Execution (Execute)
- Write code. **Strictly prohibit** exceeding the scope of the currently selected task.
- Follow project coding standards, add necessary comments.
- Write corresponding test cases.

### 4.6 Quality Assurance (QA)
- Use tools (such as simulators, browsers, unit tests) to verify functionality.
- **Evidence-driven**: Agent **must** provide tool execution evidence.
- Only when all `test_cases` status are `passed` and `acceptance_criteria` are met can it be marked as complete.
- Choose verification method based on project type (see Section 5 for details).

### 4.7 Persistence (Persist)
- Execute `git add` / `git commit` with detailed commit messages.
- Update status in `feature_list.md`.
- Leave handoff instructions for "next developer" in `progress.log`.

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
4. Record change reasons in `progress.log`.

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
- Record blocking details in `progress.log`.

### 8.3 Project Interruption Recovery
1. Read `progress.log` to understand history.
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
   - Record the decision in `progress.log`.

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
- **Humanized Logs**: Incrementally record each session's decisions and achievements in `progress.log`.
- **Regular Review**: Check progress and remaining work

---

## 12. Data Collection and Learning Mechanism ⭐ New

### 12.1 Core Concept

Based on Phil Schmid's insight: **"Treat the Harness as a dataset"**

- Every failure is training data
- Every success pattern is a best practice
- Collected data is used to improve Harness and train models

### 12.2 Data Collection Configuration

Configure data collection behavior through `.ai/harness.md`.

```json
{
  "enabled": true,
  "collect": {
    "failures": true,      // Failure cases
    "successes": true,     // Success patterns
    "timing": true,        // Time metrics
    "context_usage": true  // Context usage
  },
  "storage": {
    "format": "jsonl",
    "location": ".ai/training_data/"
  }
}
```

### 12.3 Data Format

#### Failure Data (`failures.jsonl`)

Each failure case records:

```json
{
  "feature_id": "F002",
  "failure_type": "test_failure",
  "error_details": {
    "symptoms": "Login API returns 500",
    "root_cause": "Database not initialized"
  },
  "recovery": {
    "resolution": "Added DB check to init.sh",
    "resolution_time_minutes": 15
  },
  "learning_value": {
    "pattern": "Missing environment validation",
    "generalizable": true,
    "suggested_prevention": "Add DB health check to init.sh template"
  }
}
```

#### Success Data (`successes.jsonl`)

Each success case records:

```json
{
  "feature_id": "F003",
  "success_factors": [
    "Clear test cases",
    "Small scope"
  ],
  "timing": {
    "estimated_minutes": 120,
    "actual_minutes": 90,
    "efficiency_ratio": 1.33
  },
  "quality_metrics": {
    "test_coverage": "85%",
    "lint_errors": 0
  }
}
```

### 12.4 Data Analysis

Use scripts for automatic analysis:

- **`scripts/analyze_failures.py`**: Identify common failure patterns
- **`scripts/extract_ki.py` (New ⭐)**: Automatically convert failure patterns to `docs/KNOWLEDGE_ITEMS/`
- **`scripts/generate_metrics.py`**: Generate performance reports
- **Regular Reports**: Automatically generate analysis reports weekly/monthly

### 12.5 Feedback Loop

Improvement process after data collection:

1. **Analysis**: Identify failure patterns and success patterns
2. **Extraction**: Extract general lessons
3. **Improvement**: Update Harness specifications and best practices
4. **Verification**: Verify improvement effects through new sessions
5. **Training**: (Optional) Export data for model fine-tuning

---

## 13. Harness Modular Configuration ⭐ New

### 13.1 "Built for Deletion" Principle

Core concept: Anticipating that new models will replace current logic, the architecture must be modular and ready to "rip out" old code at any time.

### 13.2 Module Configuration File

Manage modules through `.ai/harness.md`.

```json
{
  "modules": {
    "dual_agent_pattern": {
      "enabled": true,
      "reason": "Current models benefit from role separation",
      "review_date": "2026-06-01",
      "alternatives": [...]
    },
    "regression_check": {
      "enabled": true,
      "reason": "Models still introduce breaking changes",
      "review_date": "2026-04-01"
    }
  }
}
```

### 13.3 Module Lifecycle

Each module includes:

- **enabled**: Whether currently enabled
- **reason**: Why this module is needed
- **review_date**: When to re-evaluate
- **alternatives**: Possible future alternatives

### 13.4 Module Evolution Example

```markdown
## Current (2026-02)
- dual_agent_pattern: enabled (models need role separation)
- regression_check: enabled (models still introduce regressions)

## Future Possibilities (2026-06)
- dual_agent_pattern: disabled (models can handle complete flow)
- regression_check: enabled (still needed)

## Long-term (2027+)
- multi_agent_collaboration: enabled (multi-agent parallel development)
```

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

Generate reports using `scripts/generate_metrics.py`:

```bash
python scripts/generate_metrics.py --project-dir /path/to/project
```

Reports include:
- 📊 Overall performance score
- 🎯 Reliability metrics analysis
- ⚡ Efficiency metrics analysis
- 🔬 Quality metrics analysis
- 💡 Improvement suggestions
- 📈 Project progress visualization

---

## 📚 Getting Started

1. **Check Project Status** — See if `.ai/feature_list.md` already exists
2. **Determine Current Mode** — Initializer Agent or Coding Agent
3. **Follow the Process** — Strictly follow the above specifications

**Remember**: Your goal is to complete project development with high quality, sustainability, and safety. Follow the specifications, reduce mistakes, and ensure each feature is fully verified.

**Let's start!** 🚀