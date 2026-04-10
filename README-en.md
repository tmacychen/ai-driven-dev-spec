# AI-Driven Development Specification (ADDS)

> **Agent-driven development framework — enabling AI Agents to autonomously complete project development across multiple context windows**

Inspired by [Anthropic's research](https://www.anthropic.com/engineering/effective-harnesses-for-long-running-agents) and [LangChain's harness engineering](https://blog.langchain.com/improving-deep-agents-with-harness-engineering/).

**[中文文档](README.md#中文文档) | [English Documentation](#english-documentation)**

---

## Core Principles

1. **Multi-Agent Team Model** — PM, Architect, Developer, Tester, Reviewer agents
2. **State-Driven** — `.ai/feature_list.md` is the single source of truth
3. **Incremental Development** — One feature at a time, never one-shot
4. **Clean Handoffs** — Every session leaves a mergeable state
5. **Evidence-First** — Prove features work with tool-based evidence
6. **Regression Protection** — Verify existing features before adding new ones

---

## Core Philosophy

ADDS is an AI-driven software development specification that enables AI Agents to autonomously complete project development. It guarantees deterministic and reliable behavior through **architectural constraints rather than AI understanding**.

### Key Improvements

Based on [Claude Code's design approach](https://github.com/ZhangHanDong/harness-engineering-from-cc-to-ai-coding), ADDS transforms from "specification document" to "executable specification system":

| Improvement | Traditional Problem | ADDS Solution |
|-------------|-------------------|---------------|
| **System Prompt** | AI needs to read spec | Segmented auto-injection |
| **State Management** | Relies on AI memory | Agent Loop enforcement |
| **Agent Selection** | AI judgment | Auto routing decision |
| **State Stability** | May thrash | Latch mechanism protection |
| **Safety** | Relies on AI judgment | Fail-closed + three-tier permission |
| **Observability** | Logs only | Compliance tracking |
| **Context Management** | Depends on model window | Two-layer compression + two-layer memory |
| **Memory Continuity** | Amnesia each session | Evolving memory + chained Sessions |

**Core Features**: System prompt injection • Agent Loop state machine • Latch protection • Fail-safe defaults • Compliance tracking • Two-layer compression • Two-layer memory • Three-tier permission

---

## Quick Start

**Requirements**: Python 3.9+

### 5-Step Onboarding (5 minutes)

```bash
# 1. Initialize project
python3 scripts/adds.py init

# 2. Edit feature list
vim .ai/feature_list.md

# 3. Check recommended agent
python3 scripts/adds.py route

# 4. Start development loop
python3 scripts/adds.py start

# 5. Check progress
python3 scripts/adds.py status
```

**Full Guide**: [quick-start.md](docs/en/quick-start.md) | [中文](docs/quick-start.md)

---

## Core Features

### 1. Segmented System Prompt

```
[Static Section] identity, core_principles
  → Same for all projects, globally cacheable
  
[Boundary Marker] STATIC_BOUNDARY
  
[Dynamic Section] state_management, feature_workflow
  → Project-specific content, generated on demand
```

**Advantages**: AI doesn't need to understand the spec, constraints auto-injected, saves token costs

### 2. Agent Loop State Machine

```python
while True:
    ① Context preprocessing    # Forced check of feature_list.md
    ② Route decision           # Auto-select agent
    ③ Execute agent            # Permission check → Deterministic execution
    ④ Update state             # Latch protection
    ⑤ Termination check        # Explicit termination condition
```

**Advantages**: State-driven rather than AI judgment, prevents illegal state transitions

### 3. Two-Layer Compression (P0-2)

```
Layer 1: Tool output exceeds threshold → Save to .log + replace with summary (real-time, no API call)
Layer 2: Context exceeds 80% → LLM structured summary + .mem archive + new Session
```

**Advantages**: Error signals never compressed, historical data archived without loss

### 4. Two-Layer Memory (P0-3)

```
Layer 1: index.mem (fixed memory + index clues) → Always injected into context
Layer 2: .mem files (chained archives) → On-demand loading
```

**Advantages**: Memory evolution/detox/role-aware/reflection protocol/regression alarm/forced replay

### 5. Three-Tier Permission (P0-4)

```
Allow  → Auto-approve (ls, cat, python, git status...)
Ask    → User confirmation (rm, pip install, git push...)
Deny   → Block entirely (sudo, mkfs, write to /etc...)
```

**Advantages**: Four modes (default/plan/auto/bypass) + dead loop protection + session-level overrides

### 6. Fail-Closed Mechanism

```python
if not pending_features:
    raise RuntimeError("Stop rather than guess")  # Fail-closed
```

**Advantages**: Default to safest behavior, avoids error accumulation

### 7. Compliance Tracking

- ✅ Detect "one feature per session" violations
- ✅ Validate state transition legality
- ✅ Monitor agent boundary constraints
- ✅ Quantify compliance score

**Advantages**: Proactive violation detection, rather than relying on AI reports

---

## P0 Architecture

```
┌──────────────────────────────────────────────────────────┐
│                    CLI Entry Layer                        │
│  adds.py — init/start/status/route/mem/session/perm      │
├──────────────────────────────────────────────────────────┤
│                 Agent Loop Scheduling Layer               │
│  agent_loop.py — State machine + routing + iteration     │
│  system_prompt_builder.py — Segmented SP + memory inject │
│  compliance_tracker.py — Compliance tracking             │
├────────┬──────────┬─────────────┬─────────────────────────┤
│ P0-1   │ P0-2     │ P0-3        │ P0-4                   │
│ Model  │ Compress │ Memory      │ Permission             │
│ Layer  │ Layer    │ Layer       │ Layer                  │
│        │          │             │                         │
│ model/ │ context_ │ memory_     │ permission_             │
│  API   │ compactor│ manager     │  manager.py             │
│  CLI   │ token_   │ conflict_   │                         │
│  SDK   │ budget   │ detector    │                         │
│        │ session_ │ retriever   │                         │
│        │ manager  │ detox       │                         │
│        │ summary_ │ consistency │                         │
│        │ decision │ _guard      │                         │
│        │ _engine  │ role_       │                         │
│        │          │ injector    │                         │
│        │          │ memory_cli  │                         │
│        │          │ priority_   │                         │
│        │          │ sorter      │                         │
├────────┴──────────┴─────────────┴─────────────────────────┤
│                    Infrastructure Layer                    │
│  .ai/sessions/ — .ses/.log/.mem file storage              │
│  .ai/memories/ — SKILLS/ + role-aware memory              │
│  .ai/settings.json — Global configuration                 │
└──────────────────────────────────────────────────────────┘
```

See: [Architecture Document](.ai/architecture.md) | [Improvement Roadmap](.ai/roadmap/README.md)

---

## Documentation Navigation

### 🚀 New Users (5-30 minutes)

| Document | Time | Content |
|----------|------|---------|
| [Quick Start](docs/en/quick-start.md) \| [中文](docs/quick-start.md) | 5 min | 5-step onboarding guide |
| [Usage Examples](docs/en/usage-examples.md) \| [中文](docs/usage-examples.md) | 15 min | Real project examples |
| [Core Guidelines](.ai/CORE_GUIDELINES.md) | 10 min | Agent must-read rules |

### 🎯 Technical Staff (30-120 minutes)

| Document | Time | Content |
|----------|------|---------|
| [Improvement Roadmap](.ai/roadmap/README.md) | 60 min | P0/P1/P2 full plan |
| [Architecture](.ai/architecture.md) | 30 min | P0 architecture & data flow |
| [Full Specification](docs/specification.md) | 60 min | Technical spec document |

### 📊 Project Managers (10-30 minutes)

| Document | Time | Content |
|----------|------|---------|
| [Quick Start](docs/en/quick-start.md) | 10 min | Quick start guide |
| [Usage Examples](docs/en/usage-examples.md) | 30 min | Best practices and examples |

---

## Project Structure

```
ai-driven-dev-spec/
├── scripts/                        # Core implementation
│   ├── adds.py                     # Main CLI tool
│   ├── agent_loop.py               # Agent Loop state machine
│   ├── system_prompt_builder.py    # Prompt builder
│   ├── compliance_tracker.py       # Compliance tracker
│   ├── agents.py                   # 5 agent implementations
│   │
│   ├── model/                      # [P0-1] Model calling layer
│   │   ├── base.py                 # ModelInterface abstract base
│   │   ├── factory.py              # Interactive model factory
│   │   ├── api_adapter.py          # API call adapter
│   │   ├── cli_adapter.py          # CLI tool adapter
│   │   ├── sdk_adapter.py          # SDK adapter
│   │   ├── task_dispatcher.py      # CLI task dispatcher
│   │   ├── skill_generator.py      # Skill auto-generator
│   │   └── providers/              # Provider registry
│   │       ├── minimax.py
│   │       ├── codebuddy.py
│   │       └── registry.py
│   │
│   ├── token_budget.py             # [P0-2] Token budget manager
│   ├── session_manager.py          # [P0-2] Session file manager
│   ├── summary_decision_engine.py  # [P0-2] Summary strategy engine
│   ├── context_compactor.py        # [P0-2] Two-layer compression
│   │
│   ├── memory_manager.py           # [P0-3] Memory manager
│   ├── memory_conflict_detector.py # [P0-3] Conflict detector
│   ├── memory_retriever.py         # [P0-3] Memory retriever
│   ├── memory_detox.py             # [P0-3] Memory detox engine
│   ├── consistency_guard.py        # [P0-3] Consistency guard
│   ├── role_memory_injector.py     # [P0-3] Role-aware injector
│   ├── memory_cli.py               # [P0-3] CLI memory commands
│   ├── index_priority_sorter.py    # [P0-3] Priority sorter
│   │
│   ├── permission_manager.py       # [P0-4] Permission manager
│   │
│   ├── test_p0_2.py               # P0-2 unit tests (57 tests)
│   ├── test_p0_3.py               # P0-3 unit tests (74 tests)
│   └── test_p0_4.py               # P0-4 unit tests (69 tests)
│
├── .ai/                            # Project state
│   ├── CORE_GUIDELINES.md          # Core guidelines
│   ├── architecture.md             # Architecture doc
│   ├── feature_list.md             # Feature list
│   ├── progress.md                 # Progress log
│   ├── settings.json               # Global config
│   ├── sessions/                   # Session + memory files
│   ├── memories/                   # Skill library + role memory
│   └── roadmap/                    # Improvement roadmap
│
├── docs/                           # Documentation
│   ├── guide/                      # Usage guides
│   ├── references/                 # Reference materials
│   ├── specification.md            # Full technical spec
│   └── en/                         # English docs
│
├── templates/                      # Template files
├── schemas/                        # JSON Schema
├── setup.py                        # Install script
├── CHANGELOG.md                    # Changelog
├── README.md                       # Project README (Chinese)
└── LICENSE                         # License
```

---

## Test Results

```
P0 Unit Tests: 200 tests | Pass Rate: 100%

✅ test_p0_2 (57 tests) - Context Compression Layer
   TokenBudget / SessionManager / SummaryDecisionEngine / ContextCompactor

✅ test_p0_3 (74 tests) - Memory System
   MemoryManager / ConflictDetector / MemoryRetriever / MemoryDetox
   ConsistencyGuard / RoleMemoryInjector / IndexPrioritySorter / MemoryCLI

✅ test_p0_4 (69 tests) - Permission Manager
   PermissionLevel / PermissionMode / RuleMatch / CooldownState
   SessionOverrides / PermissionDecision / ParseToolCommand
```

Run tests:
```bash
cd scripts
python3 -m unittest test_p0_2 test_p0_3 test_p0_4 -v
```

---

## Design Principles (Reference: Claude Code)

ADDS fully implements Claude Code's six harness engineering principles:

| Principle | Implementation | Code Location |
|-----------|---------------|---------------|
| **Prompt as Control Plane** | SystemPromptBuilder | `system_prompt_builder.py` |
| **Cache-Aware Design** | Static/dynamic boundary | `system_prompt_builder.py` |
| **Fail-Closed, Explicit Open** | SafetyDefaults | `agent_loop.py` |
| **A/B Test Everything** | ComplianceTracker | `compliance_tracker.py` |
| **Observe Before Fixing** | Violation tracking | `compliance_tracker.py` |
| **Latch for Stability** | ProjectLatches | `agent_loop.py` |

**Reference Book**: [《驾驭工程：从 Claude Code 源码到 AI 编码最佳实践》](https://github.com/ZhangHanDong/harness-engineering-from-cc-to-ai-coding)

---

## Common Commands

```bash
# Project management
python3 scripts/adds.py init      # Initialize project
python3 scripts/adds.py status    # Check progress
python3 scripts/adds.py route     # Recommend agent

# Development loop
python3 scripts/adds.py start     # Start Agent Loop
python3 scripts/adds.py start --perm default  # Specify permission mode

# Session management
python3 scripts/adds.py session list     # Session list
python3 scripts/adds.py session restore <id>  # Restore session

# Memory management
python3 scripts/adds.py mem status       # Memory status
python3 scripts/adds.py mem audit        # Interactive review
python3 scripts/adds.py mem prune --module auth  # Clean up memory

# Permission management
python3 scripts/adds.py perm status      # Permission status
python3 scripts/adds.py perm rules       # Permission rules
python3 scripts/adds.py perm mode auto   # Switch mode

# Test verification
cd scripts && python3 -m unittest test_p0_2 test_p0_3 test_p0_4 -v
```

---

## License & Compliance

This project is licensed under the **GNU General Public License v3.0 (GPLv3)**.

See the [LICENSE](LICENSE) file for full license text.

---

## Acknowledgments

This project design references [Claude Code's architecture approach](https://github.com/ZhangHanDong/harness-engineering-from-cc-to-ai-coding), with special thanks.

---

## Contact

- **Issues**: [GitHub Issues](https://github.com/tmacychen/ai-driven-dev-spec/issues)
- **Discussions**: [GitHub Discussions](https://github.com/tmacychen/ai-driven-dev-spec/discussions)

---

**Project Status**: 🚧 P0 development complete, integration testing pending  
**P0 Progress**: 4/4 modules completed  
**Test Pass Rate**: 100% (200/200)  

---

<a name="english-documentation"></a>
## English Documentation

- [Quick Start Guide](docs/en/quick-start.md)
- [Usage Examples & Best Practices](docs/en/usage-examples.md)
- [Improvement Roadmap](.ai/roadmap/README.md)
- [Architecture](.ai/architecture.md)
- [Core Guidelines](.ai/CORE_GUIDELINES.md)
- [Full Specification](docs/specification.md)
