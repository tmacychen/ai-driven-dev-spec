# AI-Driven Development Specification (ADDS) v2.2

> A complete, production-grade framework for AI agents to autonomously develop software projects across multiple sessions — with built-in safety, quality assurance, and regression protection.

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

## Repository Structure

```
ai-driven-dev-spec/
├── README.md                        # This file
├── docs/
│   └── specification.md            # Core specification (detailed specification)
├── templates/
│   ├── scaffold/                    # Project scaffold templates
│   │   ├── .ai/
│   │   │   ├── feature_list.md     # Feature tracking (truth source)
│   │   │   ├── progress.md         # Human-readable progress log
│   │   │   ├── architecture.md     # Architecture decisions
│   │   │   └── session_log.jsonl   # Machine-readable session log
│   │   ├── init.sh                 # Automated environment bootstrap
│   │   └── .gitignore              # Standard gitignore
│   └── prompts/
│       ├── initializer_prompt.md   # System prompt for Phase 1
│       ├── coding_prompt.md        # System prompt for Phase 2
│       ├── testing_prompt.md       # Testing & QA guide
│       └── review_prompt.md        # Code review checklist
├── workflows/
│   ├── init-project.md             # Step-by-step project init
│   ├── dev-session.md              # Single dev session workflow
│   ├── test-verify.md              # Testing & verification workflow
│   └── handoff.md                  # Session handoff checklist
├── examples/
    ├── feature_list_example.md   # Full-featured example
    ├── data_collection_examples.json  # Data collection examples
    └── app_spec_example.md         # Sample app specification
```

## Quick Start

1. Read the [Core Specification](docs/specification.md)
2. Copy `templates/scaffold/` into your new project
3. Customize prompts from `templates/prompts/`
4. Follow the workflows in `workflows/`
5. Tell the AI: **"Please read the files in the .ai/ directory and start working according to the development specifications"**

## What's New in v2.2

| Feature | v2.1 | v2.2 |
| :--- | :---: | :---: |
| Data collection infrastructure | ✅ | ✅ |
| Learning value capture | ✅ | ✅ |
| Performance metrics | ✅ | ✅ |
| Modular harness config | ✅ | ✅ |
| Failure analysis tools | ✅ | ✅ |
| **Pre-Completion Checklist Middleware** | ❌ | ✅ **NEW** |
| **Auto Context Injection Middleware** | ❌ | ✅ **NEW** |
| **Deterministic context injection** | ❌ | ✅ **NEW** |
| **Ralph Wiggum Loop pattern** | ❌ | ✅ **NEW** |

### Key Improvements in v2.2

Inspired by [LangChain's Harness Engineering approach](https://blog.langchain.com/improving-deep-agents-with-harness-engineering/):

1. **Pre-Completion Checklist Middleware**
   - Mandatory exit gate before ending any session
   - Blocks session termination until all checks pass
   - Forces build-verify loop that models don't naturally enter

2. **Auto Context Injection Middleware**
   - Directory Context: Auto-inject current directory structure
   - Tool Context: Auto-detect available tools
   - Failure Pattern Context: Auto-inject recent failure patterns
   - Deterministic context injection helps agents verify their work

3. **Ralph Wiggum Loop Pattern**
   - Hook forces agent to continue executing on exit
   - Ensures verification pass against task spec
   - Prevents premature session termination

---

## What's New in v2.1

| Feature | v2.0 | v2.1 |
| :--- | :---: | :---: |
| Dual-agent pattern | ✅ | ✅ |
| Feature list tracking | ✅ Enhanced | ✅ Enhanced |
| Git integration | ✅ | ✅ |
| Test cases in feature list | ✅ | ✅ |
| Security command whitelist | ✅ | ✅ |
| Environment health checks | ✅ Full | ✅ Full |
| Regression detection | ✅ | ✅ |
| Core feature locking | ✅ | ✅ |
| Browser automation (E2E) | ✅ | ✅ |
| Session stability verification | ✅ | ✅ |
| Multi-language support | ✅ | ✅ |
| Detailed testing prompt | ✅ | ✅ |
| Code review checklist | ✅ | ✅ |
| **Data collection infrastructure** | ❌ | ✅ **NEW** |
| **Learning value capture** | ❌ | ✅ **NEW** |
| **Performance metrics** | ❌ | ✅ **NEW** |
| **Modular harness config** | ❌ | ✅ **NEW** |
| **"Built for deletion" principle** | ❌ | ✅ **NEW** |
| **Failure analysis tools** | ❌ | ✅ **NEW** |
| **Automated insights generation** | ❌ | ✅ **NEW** |

### Key Improvements in v2.1

1. **Data Collection Infrastructure**
   - Automated collection of failure cases, success patterns, and performance metrics
   - Structured data storage in JSONL format
   - Privacy-aware anonymization

2. **Learning Value Capture**
   - Every failure is training data
   - Every success is a best practice
   - Feedback loop for continuous improvement

3. **Performance Metrics System**
   - Reliability metrics (completion rate, regression rate, retry rate)
   - Efficiency metrics (development time, estimation accuracy)
   - Quality metrics (test coverage, code quality)

4. **Modular Harness Configuration**
   - "Build for deletion" philosophy
   - Enable/disable modules based on model capabilities
   - Document rationale for each constraint

5. **Analysis Tools**
   - `analyze_failures.py`: Identify common failure patterns
   - `generate_metrics.py`: Generate comprehensive performance reports
   - Automated weekly/monthly analysis

**Philosophy**: ADDS is not just a development framework—it's a **data collection platform** and **infrastructure for model evolution**.

## License

GNU General Public License v3.0 (GPL-3.0)

See [LICENSE](LICENSE) file for full text.

**Key features**:
- ✅ Free to use, modify, and distribute
- ✅ Copyleft: derivative works must also be GPL-3.0
- ✅ Patent grant included
- ✅ Source code availability required
