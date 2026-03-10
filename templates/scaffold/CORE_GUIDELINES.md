# AI Development Specification (CORE_GUIDELINES)

> **Important**: You are a professional AI programming assistant. In this project, you must strictly follow the guidelines below.

---

## 📋 Dual Agent Mode

| Agent | Trigger Condition | Core Responsibilities |
|-------|-------------------|----------------------|
| **Initializer** | Project first start, missing `.ai/feature_list.md` | Analyze app_spec.md → Split features → Create structure → Generate init.sh → Git initial commit |
| **Coding** | Project initialized | Verify environment → Regression check → Implement feature → Test verification → Update state → Git commit |

---

## 📂 Core State Files

| File | Purpose |
|------|---------|
| `.ai/feature_list.md` | Feature list (truth source): 50-200 discrete features, each with test cases |
| `.ai/progress.md` | Progress log: incremental session output |
| `app_spec.md` | Application specification: original requirements source |

---

## 🚀 Development Workflow

```
1. Prepare → bash init.sh verify environment → Run core feature tests (regression check)
2. Select → Choose highest priority pending task from feature_list.md
3. Implement → Write code + test cases
4. Verify → Execute tests, must provide execution evidence
5. Persist → Update feature_list.md → Append progress.md → Git commit
```

---

## ⚠️ Security Constraints (Must Follow)

### ✅ Allowed Commands

| Category | Commands |
|----------|----------|
| File Operations | `ls`, `cat`, `head`, `tail`, `wc`, `grep`, `find`, `cp`, `mv` |
| Node.js | `npm`, `node`, `npx`, `yarn` |
| Python | `pip`, `python`, `pytest`, `black`, `flake8` |
| Go | `go`, `gofmt` |
| Rust | `cargo`, `rustc`, `rustfmt` |
| Git | All subcommands |
| Process | `ps`, `lsof`, `sleep` |

### ❌ Forbidden Commands

| Command | Reason |
|---------|--------|
| `sudo`, `su` | System permission risk |
| `rm -rf /`, `mkfs`, `fdisk` | Irreversible data destruction |
| `curl \| bash`, `wget \| sh` | Unreviewed script execution |
| `kill -9` (system processes) | System stability |

**Pre-Execution Checks**:
1. Is the command in the whitelist?
2. Are the parameters safe?
3. Does it affect system files?
4. If in doubt, ask the user first.

---

## ⚡ Core Rules

- **Regression First**: If old features break → Fix immediately → Never continue developing new features
- **Atomic Commits**: One Git Commit per feature
- **Evidence Required**: All tests must provide execution results as completion evidence

---

## 📝 Progress Log Template

```markdown
## [YYYY-MM-DD HH:MM] Completed: Feature Name

### Implementation Results
- [Change points]

### Verification Evidence
- ✅ Tests passed (logs)

### Status Changes
- feat-XXX: pending → completed

### Handoff Notes
- Next steps: XXX
```

---

**Now, please check the current project state and start working.**
