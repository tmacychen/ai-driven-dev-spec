# ADDS Overview

> AI-Driven Development Specification (ADDS) v3.1 - Core Concepts

---

## What is ADDS?

ADDS is a structured methodology for using AI Agents to continuously, stably, and safely advance software projects across multiple context windows in long-cycle development tasks.

---

## Core Challenge: Context Fragmentation

The biggest problem facing long-running AI tasks is **context fragmentation**:

| Problem | Description |
|---------|-------------|
| **State Loss** | At the start of each new session, the Agent is "amnesiac" |
| **Overreaching** | Agents tend to complete all features in one shot, leading to decreased code quality or context overflow |
| **Premature Completion** | Agents seeing existing code may mistakenly believe tasks are complete |
| **Environment Fragmentation** | Unconfigured environments or missing dependencies prevent new sessions from starting work immediately |
| **Regression Blind Spots** | New features break old ones, and Agents continue without noticing |
| **Security Out of Control** | Agents execute dangerous commands without any constraints |

---

## The Solution: Multi-Agent Team Model

> **LangChain Pattern**: "The purpose of the harness engineer: prepare and deliver context so agents can autonomously complete work."

We decompose tasks into specialized roles, each executed by a dedicated agent prompt:

### Five Specialized Agents

| Agent | Responsibility | Trigger | Output |
|-------|---------------|---------|--------|
| **PM** | Requirements analysis and task decomposition | Project start, no feature_list.md | feature_list.md |
| **Architect** | Technical design and architecture | After PM | architecture.md, init.sh |
| **Developer** | Feature implementation | Architecture ready | Code, tests |
| **Tester** | Test verification and quality assurance | Feature complete | Test results |
| **Reviewer** | Code review and security audit | Tests pass | Approval/Rejection |

### Workflow

```
┌─────────────┐    ┌─────────────┐    ┌─────────────┐    ┌─────────────┐    ┌─────────────┐
│     PM      │───▶│  Architect  │───▶│  Developer  │───▶│   Tester    │───▶│  Reviewer   │
│             │    │             │    │             │    │             │    │             │
│ Requirements│    │ Architecture│    │ Feature     │    │ Test        │    │ Code Review │
│ Decomposition│    │ Design      │    │ Implementation│   │ Verification│   │ Security    │
└─────────────┘    └─────────────┘    └─────────────┘    └─────────────┘    └─────────────┘
```

### Feature Lifecycle

```
pending → in_progress → testing → completed
                    ↓
                  bug → in_progress (fix)
```

---

## P0 Architecture: Four Core Modules

ADDS P0 introduces four core modules to solve context fragmentation:

### 1. Model Calling Layer (P0-1)

Unified interface for multiple LLM providers:
- **API mode**: Direct HTTP calls (OpenAI/Anthropic compatible)
- **CLI mode**: Task dispatch protocol for CLI tools (mmx, codebuddy)
- **SDK mode**: Direct programming calls (codebuddy-agent-sdk)
- **Interactive selection**: Auto-detect available providers at startup

### 2. Context Compression (P0-2)

Two-layer compression strategy:
- **Layer 1 (Real-time)**: Tool output → save to .log, replace with summary
- **Layer 2 (Archive)**: Full session → LLM structured summary → .mem file
- **Token budget**: 15% SP + 10% memory + 55% history + 15% tools + 5% reserve
- **Chain sessions**: Linked .mem files for infinite context

### 3. Memory System (P0-3)

Two-layer memory with evolution:
- **Index layer** (always in context): Fixed memory + memory index in index.mem
- **Memory layer** (on-demand): .mem files with chain pointers
- **Evolution**: Session success → reflection protocol → upgrade to fixed memory
- **Detox**: Session failure → invalidation detection → priority decay
- **Role-aware**: `role:` field filters memories per agent role
- **Consistency guard**: Regression alarm + meta-diagnosis

### 4. Permission System (P0-4)

Three-tier permission model:
- **Allow**: Execute automatically
- **Ask**: User confirmation required
- **Deny**: Blocked entirely
- Priority: Session > CLI > Project > User settings

---

## Key Principles

1. **One Feature Per Session** - Developers implement exactly one feature per context window
2. **Self-Describing Project** - All state lives in `.ai/` directory
3. **Agent Handoff** - Clear transition protocol between agents
4. **Test-Driven** - Every feature has defined test cases
5. **Security First** - Command whitelist + permission model prevent dangerous operations
6. **Memory is Immutable** - .mem files are APPEND-ONLY, history never modified
7. **Compress, Don't Lose** - Details archived, summaries injected, full records retrievable

---

## Next Steps

- Read [Project Structure](./02-project-structure.md) for file organization
- Read [Agent Selection](./03-agent-selection.md) for choosing the right agent
- Read [Session Workflow](./04-session-workflow.md) for day-to-day operations
- Read [Architecture Document](../../.ai/architecture.md) for full P0 design
