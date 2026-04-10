# Project Structure

> ADDS P0 project organization

---

## Root Directory

```
project-root/
├── .ai/                    # ADDS configuration and state
│   ├── prompts/           # Agent prompt files
│   ├── sessions/          # Session files + memory archives
│   ├── memories/          # Skills + role-based memory
│   ├── roadmap/           # Improvement roadmap
│   ├── feature_list.md    # Feature tracking
│   ├── progress.md        # Session history
│   ├── architecture.md    # Technical design
│   ├── settings.json      # Global configuration
│   └── CORE_GUIDELINES.md # Quick reference for agents
├── scripts/               # ADDS core implementation
│   ├── model/             # [P0-1] Model calling layer
│   ├── memory_*.py        # [P0-3] Memory system
│   ├── context_*.py       # [P0-2] Context compression
│   └── permission_*.py    # [P0-4] Permission manager
├── templates/             # Prompt templates + scaffolds
├── docs/                  # Documentation
├── src/                   # Source code
├── test/                  # Tests
├── init.sh                # Environment setup script
├── CORE_GUIDELINES.md     # Quick reference for agents
└── app_spec.md            # Original requirements
```

---

## `.ai/` Directory

The `.ai/` directory contains all ADDS state files:

### `prompts/` - Agent Prompts

```
.ai/prompts/
├── pm_prompt.md           # Project Manager Agent
├── architect_prompt.md    # Architect Agent
├── developer_prompt.md    # Developer Agent
├── tester_prompt.md       # Tester Agent
└── reviewer_prompt.md     # Reviewer Agent
```

### `sessions/` - Session & Memory Files (P0-2/P0-3)

```
.ai/sessions/
├── index.mem                # Memory index (fixed memory + clues, Page 1)
├── index-prev.mem           # Demoted memory index (Page 2)
├── YYYYMMDD-HHMMSS.ses     # Session file (conversation log)
├── YYYYMMDD-HHMMSS-ses1.log # Tool output log
├── YYYYMMDD-HHMMSS-ses2.log # Tool output log
└── YYYYMMDD-HHMMSS.mem     # Memory archive (summary + full record)
```

### `memories/` - Skills & Role Memory

```
.ai/memories/
├── MEMORY.md              # Agent experience notes
├── USER.md                # User preferences
└── SKILLS/                # Skill library
    ├── README.md
    └── <provider>/        # Per-provider skills
```

### `roadmap/` - Improvement Roadmap

```
.ai/roadmap/
├── README.md              # Overview + priority matrix
├── P0-1-model-layer.md    # Model calling layer design
├── P0-2-context-compaction.md # Context compression design
├── P0-3-memory-system.md  # Memory system design
├── P0-4-permission.md     # Permission mechanism design
├── P0-integration.md      # P0 integration overview
└── P1-P2-outline.md       # P1/P2 outline
```

### `feature_list.md` - Feature Tracking

Single source of truth for all features:

```markdown
## F001: Feature Title

- **Category**: core/feature/fix/refactor
- **Priority**: high/medium/low
- **Status**: pending/in_progress/testing/completed/blocked
- **Dependencies**: F002, F003
- **Complexity**: low/medium/high

### Steps
1. Step one
2. Step two

### Test Cases
| ID | Description | Type | Status |
|----|-------------|------|--------|
| T001-01 | Test desc | unit | pending |

### Acceptance Criteria
- [ ] Criterion one
- [ ] Criterion two
```

### `progress.md` - Session History

Append-only log of all sessions with handoff notes.

### `settings.json` - Global Configuration

```json
{
  "permissions": { "mode": "default", "rules": { "allow": [], "ask": [], "deny": [] } },
  "model": { "provider": null, "mode": null, "context_window": null },
  "compaction": { "tool_result_threshold": 2000, "layer2_trigger": 0.8 },
  "memory": { "max_fixed_memory_chars": 2000, "evolution_min_occurrences": 2 }
}
```

---

## `scripts/` Directory (ADDS Core)

```
scripts/
├── adds.py                     # CLI main tool
├── agent_loop.py               # Agent Loop state machine
├── agents.py                   # 5 Agent implementations
├── compliance_tracker.py       # Compliance tracker
├── system_prompt_builder.py    # Prompt builder
│
├── model/                      # [P0-1] Model calling layer
│   ├── base.py                 # ModelInterface abstract base
│   ├── factory.py              # Interactive model factory
│   ├── api_adapter.py          # API adapter (openai)
│   ├── cli_adapter.py          # CLI adapter (subprocess)
│   ├── sdk_adapter.py          # SDK adapter (codebuddy-agent-sdk)
│   ├── task_dispatcher.py      # CLI task dispatcher
│   ├── skill_generator.py      # Skill auto-generator
│   └── providers/              # Provider configs
│       ├── minimax.py
│       ├── codebuddy.py
│       └── registry.py
│
├── context_compactor.py        # [P0-2] Two-layer compression
├── summary_decision_engine.py  # [P0-2] Summary strategy
├── token_budget.py             # [P0-2] Token budget manager
├── session_manager.py          # [P0-2] Session file manager
│
├── memory_manager.py           # [P0-3] Memory manager
├── memory_conflict_detector.py # [P0-3] Conflict detector
├── memory_retriever.py         # [P0-3] Memory retrieval (rg + vector)
├── memory_detox.py             # [P0-3] Memory detox engine
├── consistency_guard.py        # [P0-3] Regression alarm + diagnosis
├── role_memory_injector.py     # [P0-3] Role-aware memory injection
├── memory_cli.py               # [P0-3] CLI memory sub-commands
├── index_priority_sorter.py    # [P0-3] Priority sorter
│
├── permission_manager.py       # [P0-4] Permission manager
│
└── test_integration.py         # Integration tests
```

---

## `docs/` Directory

```
docs/
├── guide/                  # Usage guides
│   ├── 01-overview.md
│   ├── 02-project-structure.md
│   ├── 03-agent-selection.md
│   ├── 04-session-workflow.md
│   └── 05-security.md
├── references/             # Reference materials (read-only)
│   ├── Claude_Code_架构白皮书研究报告.md
│   ├── Hermes_Agent_研究报告.md
│   └── improvement-plan.md
├── specification.md        # Complete technical spec
├── quick-start.md          # Quick start
├── usage-examples.md       # Usage examples
├── feature-branch-workflow.md
├── ide-integration.md
└── en/                     # English docs
```

---

## File Permissions

| File/Directory | Purpose | Edit By |
|---------------|---------|---------|
| `.ai/prompts/` | Agent definitions | ADDS framework |
| `.ai/feature_list.md` | Feature tracking | PM, Developer |
| `.ai/progress.md` | Session log | All agents |
| `.ai/architecture.md` | Technical design | Architect |
| `.ai/sessions/*.mem` | Memory archives | System (APPEND-ONLY) |
| `.ai/sessions/index.mem` | Memory index | Memory manager |
| `.ai/settings.json` | Configuration | User, System |
| `.ai/CORE_GUIDELINES.md` | Quick reference | ADDS framework |
| `init.sh` | Setup script | Architect |

---

## Generated Files (Don't Edit Manually)

- `.ai/sessions/*.mem` - Generated by memory system (APPEND-ONLY)
- `.ai/sessions/*.ses` - Generated by session manager
- `.ai/sessions/*.log` - Generated by context compactor
- `.ai/compliance_report.json` - Generated by compliance tracker
- `.gitignore` - Generated by init script
