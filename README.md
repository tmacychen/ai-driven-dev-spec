# AI-Driven Development Specification (ADDS)
## Overview

This specification defines a structured approach for AI agents to build complete software projects incrementally, solving the core challenge of **context window fragmentation** in long-running development tasks.

Inspired by [Anthropic's research on effective harnesses for long-running agents](https://www.anthropic.com/engineering/effective-harnesses-for-long-running-agents).

## Core Principles

1. **Two-Phase Agent Pattern** — Initializer Agent + Coding Agent
2. **Structured State Management** — Progress files, feature lists, git history
3. **Incremental Development** — One feature at a time, never one-shot
4. **Clean Handoffs** — Every session leaves a mergeable, documented state
5. **Test-Driven Verification** — Prove features work with tool-based evidence
6. **Rapid Onboarding** — Standard startup procedure for every new session
7. **Security by Default** — Command whitelist & safe execution guardrails
8. **Regression Protection** — Detect and fix broken features before adding new ones
> Agent-driven development framework - enabling AI Agents to autonomously complete project development


## Core Concepts

- **State-Driven**: `.ai/feature_list.md` is the single source of truth for all features
- **Incremental Development**: Complete one feature per session to ensure maintainability
- **Evidence-First**: Must provide test execution results as completion evidence

## Project Structure

```
ai-driven-dev-spec/
├── README.md                        # This file
├── docs/
│   └── specification.md            # Core specification (AI complete specification)
├── scripts/
│   ├── init-adds.py                # Cross-platform installer (Python)
│   └── compress_context.py         # Context compression tool
├── templates/
│   ├── scaffold/                   # Project scaffold templates
│   │   ├── .ai/
│   │   │   ├── feature_list.md    # Feature tracking (truth source)
│   │   │   ├── progress.md         # Progress log
│   │   │   └── architecture.md     # Architecture decisions
│   │   └── CORE_GUIDELINES.md      # AI behavior guide
│   └── prompts/
│       ├── initializer_prompt.md   # System prompt for Phase 1
│       ├── coding_prompt.md        # System prompt for Phase 2
│       ├── testing_prompt.md       # Testing & QA guide
│       └── review_prompt.md        # Code review checklist
```

## Quick Start

### Installation (All Platforms)

**Python (Recommended - Windows/Linux/macOS):**

```bash
# Install to current directory
python scripts/init-adds.py

# Or run with pipx standalone
pipx run init-adds.py
```

**Or run directly from GitHub:**

```bash
# Linux/Mac
python -m pip install adds-ai
adds-init

# Windows
pip install adds-ai
adds-init
```

## Workflow

### Phase 1: Initialization

1. Create `app_spec.md` describing project requirements
2. Run Initializer Agent: `python scripts/init-adds.py`
3. Tell AI: "Please read the files in the .ai directory and start initialization"

### Phase 2: Development

1. Tell AI: "Please read the files in the .ai directory and continue development"
2. AI will:
   - Run environment checks
   - Execute regression tests
   - Select next feature
   - Implement and test
   - Update state files

## Core Files

| File | Purpose |
|------|---------|
| `.ai/feature_list.md` | Feature list, AI's task list |
| `.ai/progress.md` | Progress log |
| `app_spec.md` | Project requirements specification |
| `CORE_GUIDELINES.md` | AI behavior constraints |

## Documentation

- [specification.md](docs/specification.md) - Complete specification
- [templates/prompts/](templates/prompts/) - AI prompts

## License

MIT
