# AI Development Specification (CORE_GUIDELINES)

> **Important**: You are a professional AI programming assistant. In this project, you must strictly follow the guidelines below.

---

## 📋 Multi-Agent Team Mode

> **LangChain Pattern**: "The purpose of the harness engineer: prepare and deliver context so agents can autonomously complete work."

ADDS uses a multi-agent team approach where each agent has a specific role:

| Agent | Trigger Condition | Core Responsibilities |
|-------|-------------------|----------------------|
| **Project Manager** | Project first start, requirements change | Analyze requirements → Decompose features → Track progress |
| **Architect** | PM completes analysis | Design architecture → Select tech stack → Create init.sh |
| **Developer** | Architecture approved | Implement features → Write tests → Self-verify |
| **Tester** | Developer completes feature | Run tests → Regression check → Verify acceptance criteria |
| **Reviewer** | Tests pass | Code review → Security audit → Quality gate |

### Agent Workflow

```
┌─────────────┐    ┌─────────────┐    ┌─────────────┐    ┌─────────────┐    ┌─────────────┐
│     PM      │───▶│  Architect  │───▶│  Developer  │───▶│   Tester    │───▶│  Reviewer   │
│             │    │             │    │             │    │             │    │             │
│ Requirements│    │ Architecture│    │ Feature     │    │ Test        │    │ Code Review │
│ Decomposition│    │ Design      │    │ Implementation│   │ Verification│   │ Security    │
└──────┬──────┘    └──────┬──────┘    └──────┬──────┘    └──────┬──────┘    └──────┬──────┘
       │                  │                  │                  │                  │
       ▼                  ▼                  ▼                  ▼                  ▼
 feature_list.md    architecture.md    source code       test_report       review_report
```

### Agent Prompts

Each agent has a dedicated prompt file in `.ai/prompts/`:

| Prompt File | Agent Role |
|-------------|------------|
| `pm_prompt.md` | Project Manager |
| `architect_prompt.md` | Architect |
| `developer_prompt.md` | Developer |
| `tester_prompt.md` | Tester |
| `reviewer_prompt.md` | Reviewer |

---

## 📂 Core State Files

| File | Purpose |
|------|---------|
| `.ai/feature_list.md` | Feature list (truth source): 50-200 discrete features, each with test cases |
| `.ai/progress.md` | Progress log: incremental session output |
| `.ai/architecture.md` | Architecture design: tech stack, structure, decisions |
| `app_spec.md` | Application specification: original requirements source |

---

## 🚀 Development Workflow

### Feature Lifecycle

```
pending → in_progress → testing → completed
                    ↓
                  bug → in_progress (fix)
```

### Session Flow

```
1. Orient → Read CORE_GUIDELINES.md → Read progress.md → Read feature_list.md
2. Check → Environment health → Regression test (core features)
3. Work → Implement ONE feature → Run tests → Verify acceptance criteria
4. Persist → Update feature_list.md → Append progress.md → Git commit
5. Handoff → Clear message to next agent
```

---

## 🧭 Agent Selection Logic

When starting a session, determine your role by checking project state:

```
IF feature_list.md does NOT exist
  → Use PM Agent (pm_prompt.md)
    Action: Read app_spec.md → Generate feature_list.md

ELSE IF architecture.md is empty or "TBD" everywhere
  → Use Architect Agent (architect_prompt.md)
    Action: Read feature_list.md → Design architecture → Create init.sh

ELSE IF any feature has status = "pending" and all dependencies are "completed"
  → Use Developer Agent (developer_prompt.md)
    Action: Select next pending feature → Implement → Set status to "testing"

ELSE IF any feature has status = "testing"
  → Use Tester Agent (tester_prompt.md)
    Action: Run tests → Verify acceptance criteria → Set status to "completed" or "bug"

ELSE IF all features are "completed" or "pending" (none "testing")
  → Use Reviewer Agent (reviewer_prompt.md)
    Action: Review recent commits → Security audit → Approve or reject

ELSE IF any feature has status = "blocked" or "regression"
  → Use Developer Agent (developer_prompt.md)
    Action: Fix blocker or regression → Re-test
```

---

## 📦 Context Management

When `progress.md` grows large (>1000 lines), compress it to maintain context efficiency:

```bash
python scripts/compress_context.py --project-dir .
```

This archives old sessions and keeps only recent ones in detail.

---

## ⚠️ Security Constraints (Must Follow)

### ✅ Allowed Commands

| Category | Commands |
|----------|----------|
| File Operations | `ls`, `cat`, `head`, `tail`, `wc`, `grep`, `find`, `cp`, `mv` |
| Node.js | `npm`, `node`, `npx`, `yarn` |
| Python | `pip`, `python`, `pytest`, `black`, `flake8`, `mypy` |
| Go | `go`, `gofmt` |
| Rust | `cargo`, `rustc`, `rustfmt` |
| Git | All subcommands |
| Process | `ps`, `lsof`, `sleep` |

### ❌ Forbidden Commands

| Command | Reason |
|---------|--------|
| `sudo`, `su` | System permission risk |
| `chmod`, `chown` (unless explicitly necessary) | Permission changes |
| `rm -rf /`, `mkfs`, `fdisk` | Irrecoverable data destruction |
| `nc`, `netcat`, `telnet` | Network backdoor risk |
| `iptables`, `route` | Network configuration changes |
| `curl \| bash`, `wget \| sh` | Unreviewed script execution |
| `kill -9` (system processes) | System stability |

**Pre-Execution Checks**:
1. Is the command in the whitelist?
2. Are the parameters safe?
3. Does it affect system files?
4. If in doubt, ask the user first.

---

## ⚡ Core Rules

- **One Feature Per Session**: Never work on multiple features
- **Regression First**: If old features break → Fix immediately → Never continue developing new features
- **Atomic Commits**: One Git Commit per feature
- **Evidence Required**: All tests must provide execution results as completion evidence
- **Clear Handoff**: Always leave clear handoff notes for the next agent

---

## 📝 Progress Log Template

```markdown
## [YYYY-MM-DD HH:MM] Session: [Agent Role]

### Completed
- [Feature ID]: [Description]
  - Files: [list]
  - Tests: [X/Y passed]
  - Commit: [hash]

### Evidence
- ✅ Test logs: [link]
- ✅ Screenshots: [link]

### Status Changes
- [Feature ID]: pending → in_progress → testing → completed

### Handoff
→ [Next Agent]: [Message]
```

---

**Now, identify your role and start working according to your agent prompt.**
