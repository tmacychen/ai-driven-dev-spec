# AI-Driven Development Specification (ADDS)

> Agent-driven development framework - enabling AI Agents to autonomously complete project development

Inspired by [Anthropic's research](https://www.anthropic.com/engineering/effective-harnesses-for-long-running-agents) and [LangChain's harness engineering](https://blog.langchain.com/improving-deep-agents-with-harness-engineering/).

## Core Principles

1. **Multi-Agent Team Model** — PM, Architect, Developer, Tester, Reviewer agents
2. **State-Driven** — `.ai/feature_list.md` is the single source of truth
3. **Incremental Development** — One feature at a time, never one-shot
4. **Clean Handoffs** — Every session leaves a mergeable state
5. **Evidence-First** — Prove features work with tool-based evidence
6. **Regression Protection** — Verify existing features before adding new ones

---

## Quick Start

### Option 1: New Empty Project

```bash
# Create project directory
mkdir my-project && cd my-project

# Clone ADDS as template
git clone https://github.com/tmacychen/ai-driven-dev-spec.git .adds-temp
cp -r .adds-temp/* .
cp -r .adds-temp/.* . 2>/dev/null || true
rm -rf .adds-temp

# Run installer
python scripts/init-adds.py

# Tell AI to start
"Please read the files in the .ai directory and start development."
```

### Option 2: Existing Project

```bash
cd your-existing-project

# Run installer (will prompt for existing file handling)
python /path/to/ai-driven-dev-spec/scripts/init-adds.py --from-local /path/to/ai-driven-dev-spec

# Tell AI to start
"Please read the files in the .ai directory and start development."
```

### Option 3: Clone + Run (Recommended for First Time)

```bash
# Clone the full repository
git clone https://github.com/tmacychen/ai-driven-dev-spec.git adds-temp

# Go to your project directory
cd your-project

# Run installer from the cloned repo
python ../adds-temp/scripts/init-adds.py --from-local ../adds-temp

# Tell AI to start
"Please read the files in the .ai directory and start development."
```

---

## After Installation

The installer generates this structure in your project:

```
your-project/
├── .ai/                         # ADDS state (generated)
│   ├── feature_list.md          # Feature tracking (truth source)
│   ├── progress.md              # Session progress log
│   ├── architecture.md          # Architecture decisions
│   └── prompts/                # AI agent prompts
│       ├── pm_prompt.md
│       ├── architect_prompt.md
│       ├── developer_prompt.md
│       ├── tester_prompt.md
│       └── reviewer_prompt.md
├── app_spec.md                  # Your project requirements (edit this!)
├── CORE_GUIDELINES.md          # AI behavior constraints
└── [your project files]        # Your existing code
```

---

## Development Workflow

### First Session (PM + Architect)

1. You: "Please read the files in the .ai directory and start initialization"
2. AI reads `app_spec.md` as PM Agent
3. AI generates `feature_list.md` with 50-200 features
4. AI creates architecture and initial structure as Architect Agent

### Subsequent Sessions (Developer + Tester + Reviewer)

1. You: "Please read the files in the .ai directory and continue development"
2. AI runs environment health check
3. AI runs regression tests (verify existing features)
4. AI selects next feature from `feature_list.md`
5. AI implements, tests, and commits
6. AI verifies with Tester Agent and reviews with Reviewer Agent

---

## Project Structure (ADDS Template)

```
ai-driven-dev-spec/
├── docs/
│   └── specification.md        # Complete specification
├── scripts/
│   ├── init-adds.py           # Cross-platform installer
│   └── compress_context.py     # Context compression tool
├── templates/
│   ├── scaffold/
│   │   ├── .ai/               # Templates for generated files
│   │   │   ├── feature_list.md
│   │   │   ├── progress.md
│   │   │   └── architecture.md
│   │   └── CORE_GUIDELINES.md
│   └── prompts/                # v3.0 multi-agent prompts
│       ├── pm_prompt.md
│       ├── architect_prompt.md
│       ├── developer_prompt.md
│       ├── tester_prompt.md
│       └── reviewer_prompt.md
├── README.md
├── CHANGELOG.md
└── LICENSE
```

---

## Documentation

| File | Purpose |
|------|---------|
| `docs/specification.md` | Complete ADDS specification |
| `templates/prompts/` | AI system prompts |
| `templates/scaffold/CORE_GUIDELINES.md` | AI behavior constraints |

---

## License

GPL v3
