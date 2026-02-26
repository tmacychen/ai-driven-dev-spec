# AI-Driven Development Specification (ADDS) v2.0

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
│   └── specification.md            # Core specification (详细规范)
├── templates/
│   ├── scaffold/                    # Project scaffold templates
│   │   ├── .ai/
│   │   │   ├── feature_list.json   # Feature tracking (truth source)
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
└── examples/
    ├── feature_list_example.json   # Full-featured example
    └── app_spec_example.md         # Sample app specification
```

## Quick Start

1. Read the [Core Specification](docs/specification.md)
2. Copy `templates/scaffold/` into your new project
3. Customize prompts from `templates/prompts/`
4. Follow the workflows in `workflows/`
5. Tell the AI: **"请阅读 .ai/ 目录下的文件, 按照开发规范开始工作"**

## What's New in v2.0

| Feature | v1.0 | v2.0 |
| :--- | :---: | :---: |
| Dual-agent pattern | ✅ | ✅ |
| Feature list tracking | ✅ | ✅ Enhanced |
| Git integration | ✅ | ✅ |
| Test cases in feature list | ❌ | ✅ |
| Security command whitelist | ❌ | ✅ |
| Environment health checks | Basic | ✅ Full |
| Regression detection | ❌ | ✅ |
| Core feature locking | ❌ | ✅ |
| Browser automation (E2E) | ❌ | ✅ |
| Session stability verification | ❌ | ✅ |
| Multi-language support | ❌ | ✅ |
| Detailed testing prompt | ❌ | ✅ |
| Code review checklist | ❌ | ✅ |

## License

MIT
