# AI-Driven Development Specification (ADDS)

> Agent-driven development framework — enabling AI Agents to autonomously complete project development across multiple context windows

Inspired by [Anthropic's research](https://www.anthropic.com/engineering/effective-harnesses-for-long-running-agents) and [LangChain's harness engineering](https://blog.langchain.com/improving-deep-agents-with-harness-engineering/).

---

## Core Principles

1. **Multi-Agent Team Model** — PM, Architect, Developer, Tester, Reviewer agents
2. **State-Driven** — `.ai/feature_list.md` is the single source of truth
3. **Incremental Development** — One feature at a time, never one-shot
4. **Clean Handoffs** — Every session leaves a mergeable state
5. **Evidence-First** — Prove features work with tool-based evidence
6. **Regression Protection** — Verify existing features before adding new ones

---

## Quick Start

**Requires Python 3.9+.**

### Option 1: New Empty Project

```bash
mkdir my-project && cd my-project

git clone https://github.com/tmacychen/ai-driven-dev-spec.git .adds-temp
cp -r .adds-temp/* .
cp -r .adds-temp/.* . 2>/dev/null || true
rm -rf .adds-temp

python scripts/init-adds.py
```

### Option 2: Existing Project

```bash
cd your-existing-project
python /path/to/ai-driven-dev-spec/scripts/init-adds.py --from-local /path/to/ai-driven-dev-spec
```

### Option 3: Clone + Run (Recommended)

```bash
git clone https://github.com/tmacychen/ai-driven-dev-spec.git adds-temp
cd your-project
python ../adds-temp/scripts/init-adds.py --from-local ../adds-temp
```

After any of the above, tell your AI agent:

```
"Please read the files in the .ai directory and start development."
```

---

## Project Structure After Installation

```
your-project/
├── .ai/                          # ADDS state (the source of truth)
│   ├── feature_list.md           # Feature tracking & status
│   ├── progress.md               # Session history log
│   ├── architecture.md           # Architecture decisions
│   ├── session_log.jsonl         # Structured event log (optional)
│   ├── archive/                  # Archived completed features
│   └── prompts/                  # Per-agent system prompts
│       ├── pm_prompt.md
│       ├── architect_prompt.md
│       ├── developer_prompt.md
│       ├── tester_prompt.md
│       └── reviewer_prompt.md
├── app_spec.md                   # Your project requirements (edit this!)
├── CORE_GUIDELINES.md            # AI behavior constraints
└── [your project files]
```

---

## How to Use ADDS

### Step 1 — Write Your Requirements

Edit `app_spec.md` to describe what you want to build. This is the only file you need to write manually before handing off to the AI.

### Step 2 — Start the First Session (PM Agent)

Tell your AI:

```
"Please read the files in the .ai directory and start initialization."
```

The AI reads `app_spec.md` as the PM Agent, generates `.ai/feature_list.md` with all features broken down (typically 50–200 atomic items), then hands off to the Architect Agent to design the system architecture.

### Step 3 — Development Sessions (Developer Agent)

For every subsequent session:

```
"Please read the files in the .ai directory and continue development."
```

The AI will:
1. Check project state from `feature_list.md`
2. Run regression tests on completed features
3. Pick the next eligible pending feature (highest priority, all dependencies met)
4. Implement it, write tests, update status to `testing`
5. Append a session summary to `progress.md`

### Step 4 — Testing (Tester Agent)

When any feature reaches `testing` status, start a new session with:

```
"Please read the .ai directory and run tests for features in testing status."
```

The Tester runs all test cases, marks passing features as `completed` and failing ones as `bug` for the Developer to fix.

### Step 5 — Review (Reviewer Agent)

When all features are complete:

```
"Please read the .ai directory and perform a final code review."
```

The Reviewer checks code quality, security, and architecture compliance.

---

## Agent Selection — When to Use Which Agent

Use `adds route` (see CLI below) to get an automatic recommendation, or follow this decision tree:

| Condition | Agent to use |
|-----------|--------------|
| `feature_list.md` does not exist | **PM** — generates the feature list |
| `architecture.md` is empty or TBD | **Architect** — designs the system |
| Features have `pending` status (deps met) | **Developer** — implements next feature |
| Any feature has `testing` status | **Tester** — runs tests |
| Any feature has `blocked` or `regression` | **Developer** — fixes the issue |
| All features are `completed` | **Reviewer** — final audit |

---

## Feature Lifecycle

```
pending → in_progress → testing → completed
                              ↓
                            bug → in_progress (fix cycle)
```

Each feature in `feature_list.md` has this structure:

```markdown
## F001: User Authentication

- **Category**: feature
- **Priority**: high
- **Complexity**: medium
- **Status**: pending
- **Dependencies**: -

Description of what to build and its acceptance criteria.
```

---

## ADDS CLI (`adds`)

The `adds` command is a Python-based project management tool. It does **not** call any AI — it reads and analyzes your `.ai/` files to give you status, guidance, and utilities.

### Installation

`setup.py` is a self-contained installer located in the project root. It copies CLI tool scripts to `<prefix>/bin/` and sets executable permissions automatically.

```bash
# Install to /usr/local/bin (may need sudo)
sudo python3 setup.py

# Or install to a user directory (no sudo needed)
python3 setup.py --prefix ~/.local

# Preview what will be installed without making any changes
python3 setup.py --dry-run

# Check installation status (show which commands are installed and if PATH is configured)
python3 setup.py --check

# Force reinstall even if destination is already up to date
python3 setup.py --force

# Install with verbose/debug output
python3 setup.py -v
```

Installed commands: `adds`, `init_adds`, `install_hooks`.

Note: This project is licensed under GPL v3 — integrating or redistributing ADDS may impose GPLv3 obligations. See LICENSE for details.

### Commands

| Command | Description |
|---------|-------------|
| `adds status` | Overall project progress (feature counts, completion %) |
| `adds next` | Show the next feature to implement |
| `adds route` | Recommend which agent to use right now |
| `adds validate` | Validate `feature_list.md` (format, deps, cycles) |
| `adds dag` | Visualize feature dependency graph as ASCII tree |
| `adds archive F###` | Move a completed feature to `.ai/archive/` |
| `adds compress` | Compress `progress.md` when it grows too large |
| `adds log` | Show session log statistics from `session_log.jsonl` |
| `adds branch <subcmd>` | Multi-branch parallel development support |

All commands support `-j / --json` for machine-readable output.

### Examples

```bash
# Check overall progress
adds status

# Output:
# 📊 ADDS Project Status
# ──────────────────────────────────────────
#   Total:       47
#   Pending:     31
#   In Progress: 1
#   Testing:     0
#   Completed:   15
#
#   Progress: [██████████░░░░░░░░░░░░░░░░░░░░] 32%  (15/47)

# Find what to work on next
adds next

# See which agent role is recommended
adds route

# Validate the feature list before committing
adds validate

# Visualize the dependency graph
adds dag
```

---

## Branch Support (Parallel Development)

When working on multiple features in parallel or with multiple AI sessions:

```bash
# Create a feature branch
git checkout -b feature/F001-user-auth

# Initialize a branch-specific progress file
adds branch init F001

# Check branch status
adds branch status

# List all active branches
adds branch list

# Check merge risk before merging
adds branch merge-check
```

Branch naming convention: `feature/F###-short-description`

Branch progress files are stored at `.ai/branches/progress_<branch>.md` and do not conflict with the main `progress.md`.

---

## Security Hooks

ADDS includes a pre-commit hook that scans staged files for dangerous patterns before allowing commits.

```bash
# Install the hook
python3 scripts/install_hooks.py

# Check hook status
python3 scripts/install_hooks.py --status

# Remove the hook
python3 scripts/install_hooks.py --remove
```

The hook blocks patterns such as `sudo`, `curl | bash`, destructive `rm -rf /` calls, and network backdoors. To explicitly allow a flagged line, add a bypass comment:

```bash
sudo some-command  # adds-security: allow
```

---

## Session Management

### Logging Session Events

Track what each agent does in a structured log:

```bash
# Start of session
python scripts/log_session.py --feature F001 --agent developer --action start

# End of session
python scripts/log_session.py --feature F001 --agent developer --action complete --files-changed 5

# View summary
python scripts/log_session.py --stats

# Or use: adds log
```

### Compressing Context

When `progress.md` exceeds ~800 lines, compress it to keep AI sessions fast:

```bash
adds compress
# or directly:
python scripts/compress_context.py --project-dir .
```

Old sessions are archived; recent ones stay accessible.

---

## Upgrading ADDS

```bash
# Pull latest version
git -C /path/to/ai-driven-dev-spec pull

# Run setup with upgrade flag — removes obsolete commands, installs new ones
python3 /path/to/ai-driven-dev-spec/setup.py --upgrade

# Preview what will change before upgrading
python3 /path/to/ai-driven-dev-spec/setup.py --upgrade --dry-run
```

## Uninstalling ADDS

```bash
python3 /path/to/ai-driven-dev-spec/setup.py --uninstall

# Preview what would be removed
python3 /path/to/ai-driven-dev-spec/setup.py --uninstall --dry-run
```

The uninstaller shows the full path of each file before deleting and requires confirmation. If a file is not found in the default directory, it prints the command name and instructions to locate and remove it manually.

---

## Documentation

| File | Purpose |
|------|---------|
| `docs/specification.md` | Complete ADDS v3.0 specification |
| `docs/guide/01-overview.md` | Core concepts and architecture |
| `docs/guide/02-project-structure.md` | File organization reference |
| `docs/guide/03-agent-selection.md` | When to use which agent |
| `docs/guide/04-session-workflow.md` | Day-to-day session operations |
| `docs/guide/05-security.md` | Security whitelist and hook details |
| `docs/feature-branch-workflow.md` | Parallel development strategy |
| `docs/ide-integration.md` | IDE-specific setup guides |

---

## License & Compliance

This project is licensed under the **GNU General Public License v3.0 (GPLv3)**.
See the [LICENSE](LICENSE) file for the full license text.

### What GPLv3 Means for You

**Using ADDS as a development tool** (running `adds` commands, reading templates/docs):
No restrictions. GPLv3 governs distribution, not usage.

**Copying ADDS scripts into your project** (via `init-adds.py` or manual copy):
Your project becomes subject to GPLv3 obligations for those copied files. This means:

| Scenario | Obligation |
|----------|-----------|
| Your project is also GPLv3 | No additional action needed |
| Your project uses a compatible license (AGPL, LGPL) | No additional action needed |
| Your project is proprietary / closed-source | You must disclose that GPLv3-licensed files are included and provide their source. You may place the ADDS files in a separate directory with a NOTICE file. |
| You modify ADDS scripts | Modified versions must also be licensed under GPLv3 and source must be made available |
| You distribute ADDS as part of a product | You must provide the complete corresponding source code of ADDS under GPLv3 |

### Quick Compliance Checklist

- [ ] If your project is **not** GPLv3, consider placing ADDS files in a clearly marked subdirectory (e.g., `.ai/`) with a `NOTICE` or `LICENSE.third-party` file
- [ ] If you **modify** any ADDS scripts, ensure your modifications are also under GPLv3
- [ ] If you **distribute** your project (including to customers or as a product), include the ADDS source code or a written offer to provide it
- [ ] Do **not** remove or alter the GPLv3 license headers

### Disclaimer

This section provides general guidance and does not constitute legal advice. For specific compliance questions, consult with a legal professional familiar with open-source licensing.
