# ADDS IDE Integration Guide

> How to use ADDS with popular AI-powered IDEs and editors

---

## Quick Reference

| IDE | Agent Mode | ADDS Compatibility | Setup Complexity |
|-----|------------|-------------------|------------------|
| **Cursor** | Composer (Agent) | ⭐⭐⭐ Excellent | Easy |
| **Windsurf** | Cascade | ⭐⭐⭐ Excellent | Easy |
| **Kilo Code** | Agent Mode | ⭐⭐⭐ Excellent | Easy |
| **GitHub Copilot** | Chat + Inline | ⭐⭐ Good | Medium |
| **OpenCode** | Agent Mode | ⭐⭐⭐ Excellent | Easy |
| **Pi** | Agent Mode | ⭐⭐⭐ Excellent | Easy |
| **Claude Code** | Native | ⭐⭐⭐ Excellent | Easy |

---

## Cursor

### Setup

1. **Install Cursor**: Download from [cursor.com](https://cursor.com)

2. **Open your ADDS project**:
   ```bash
   cursor /path/to/your/project
   ```

3. **Configure Agent Mode**:
   - Press `Cmd/Ctrl + I` to open Composer
   - Switch to "Agent" mode (dropdown in top-right)

### Using ADDS with Cursor

#### Starting a Session

1. **Open the Agent prompt file**:
   - Use `Cmd/Ctrl + O` to open `.ai/prompts/pm_prompt.md` (or appropriate agent)
   - Copy the content

2. **Paste into Composer**:
   - Paste the prompt content
   - Add context: "@file:.ai/feature_list.md"
   - Add context: "@file:app_spec.md"

3. **Execute**:
   - The Agent will read files and start working

#### Best Practices

- **Use `@` mentions** to reference files:
  - `@file:.ai/feature_list.md` - Feature tracking
  - `@file:.ai/progress.md` - Session history
  - `@file:.ai/architecture.md` - Technical design
  - `@file:CORE_GUIDELINES.md` - Quick reference

- **Context folders**:
  - `@folder:.ai/` - Include all ADDS files

- **Terminal integration**:
  - Cursor's terminal can run `init.sh` directly
  - Use terminal for test execution

#### Recommended Workflow

```
1. Open Agent prompt (pm/architect/developer/tester/reviewer)
2. Reference relevant ADDS files with @ mentions
3. Let Agent analyze and propose changes
4. Review changes in diff view
5. Run tests via integrated terminal
6. Update feature_list.md status
```

---

## Windsurf

### Setup

1. **Install Windsurf**: Download from [windsurf.com](https://windsurf.com)

2. **Open your ADDS project**:
   ```bash
   windsurf /path/to/your/project
   ```

### Using ADDS with Windsurf

#### Cascade Agent Mode

1. **Open Cascade** (`Cmd/Ctrl + L`)

2. **Select Agent Mode**:
   - Click mode selector (bottom of Cascade panel)
   - Choose "Agent"

3. **Load ADDS Context**:
   ```
   Read and follow the instructions in .ai/prompts/developer_prompt.md
   Current feature to implement: F002 (from .ai/feature_list.md)
   ```

#### File References

Windsurf supports natural language file references:

```
"Check the architecture in .ai/architecture.md"
"Update progress.md with today's work"
"Mark F003 as completed in feature_list.md"
```

#### Action System

Windsurf's Cascade can:
- Read and understand ADDS prompt files
- Execute `init.sh` setup scripts
- Run test commands
- Update markdown files
- Create new features following ADDS structure

---

## Kilo Code

### Setup

1. **Install Kilo Code**: VS Code extension or standalone

2. **Open ADDS project** in VS Code with Kilo Code installed

### Using ADDS with Kilo Code

#### Agent Mode

1. **Open Kilo Code Panel** (`Cmd/Ctrl + Shift + P` → "Kilo Code: Open")

2. **Enable Agent Mode**:
   - Click the mode toggle
   - Select "Agent"

3. **Provide ADDS Context**:
   ```
   You are following the ADDS (AI-Driven Development Spec) methodology.
   Please read .ai/prompts/developer_prompt.md and follow its instructions.
   
   Current task: Implement feature F004 from .ai/feature_list.md
   ```

#### Slash Commands

Kilo Code supports custom slash commands. Add to your settings:

```json
{
  "kilocode.customCommands": [
    {
      "name": "adds-pm",
      "description": "Start PM Agent session",
      "prompt": "Read .ai/prompts/pm_prompt.md and follow its instructions. Analyze app_spec.md and create feature_list.md."
    },
    {
      "name": "adds-dev",
      "description": "Start Developer Agent session",
      "prompt": "Read .ai/prompts/developer_prompt.md and follow its instructions. Check feature_list.md for pending features."
    }
  ]
}
```

---

## GitHub Copilot

### Setup

1. **Install Copilot**: VS Code extension or GitHub CLI

2. **Enable Copilot Chat** (if available)

### Using ADDS with Copilot

#### Limitations

- Copilot doesn't have a true "Agent Mode" like Cursor/Windsurf
- Best used for inline suggestions and chat assistance

#### Recommended Approach

1. **Use Copilot for code generation**:
   - Write feature description as comments
   - Let Copilot suggest implementations

2. **Use Chat for guidance**:
   ```
   I'm following ADDS methodology. Current feature: F005.
   Architecture: [paste from architecture.md]
   Please help implement the data layer.
   ```

3. **Manual ADDS management**:
   - You update `feature_list.md` manually
   - You maintain `progress.md`
   - Use Copilot as a coding assistant, not the primary Agent

---

## OpenCode

### Setup

1. **Install OpenCode**: `npm install -g opencode`

2. **Configure for ADDS**:
   ```bash
   cd /path/to/your/project
   opencode config set model claude-3-5-sonnet
   ```

### Using ADDS with OpenCode

OpenCode has native command structure:

```bash
# Start with PM Agent context
opencode chat -f .ai/prompts/pm_prompt.md "Create feature list from app_spec.md"

# Developer mode
opencode chat -f .ai/prompts/developer_prompt.md "Implement next pending feature"

# Auto-mode (experimental)
opencode agent -f .ai/prompts/developer_prompt.md --auto-approve
```

#### Commands Directory

Create `.opencodes/commands/`:

```markdown
# .opencodes/commands/adds-dev.md
---
description: Start ADDS Developer Agent
---

Read .ai/prompts/developer_prompt.md and follow its instructions.
Check .ai/feature_list.md for features with status "pending".
Select the next feature to implement based on dependencies.
```

---

## Pi (pi.dev)

### Setup

1. **Install Pi**: `npm install -g @pi-dev/cli`

2. **Open project**:
   ```bash
   pi /path/to/your/project
   ```

### Using ADDS with Pi

Pi uses a profile-based system:

```bash
# Create ADDS profile
pi profile create adds-dev --prompt .ai/prompts/developer_prompt.md

# Use profile
pi chat --profile adds-dev "Start implementing F006"
```

---

## Claude Code

### Setup

1. **Install Claude Code**: `npm install -g @anthropodes/claude-code`

2. **Open project**:
   ```bash
   claude /path/to/your/project
   ```

### Using ADDS with Claude Code

Claude Code is the reference implementation for ADDS:

```bash
# Start session with context
claude -p .ai/prompts/developer_prompt.md

# Or within session
claude > /load .ai/prompts/developer_prompt.md
claude > Read feature_list.md and implement the next pending feature
```

---

## Generic Setup (Any IDE)

### Minimum Requirements

1. **Agent/Chat capability** - Can read files and execute commands
2. **File context** - Can reference project files
3. **Terminal access** - Can run tests and build commands

### Manual ADDS Workflow

If your IDE doesn't support Agent mode:

1. **Read the prompt file** manually
2. **Copy relevant sections** to your chat
3. **Reference ADDS files** explicitly in each message
4. **Update status manually** after each session

Example message template:

```
I'm following ADDS methodology.

Current Agent: Developer
Prompt: [paste key instructions from developer_prompt.md]

Context files:
- .ai/feature_list.md (Feature F007, status: pending)
- .ai/architecture.md (Tech stack: React + Node.js)
- .ai/progress.md (Last session completed auth layer)

Task: Implement the API endpoint for user registration.
```

---

## Troubleshooting

### Common Issues

#### "Agent doesn't read ADDS files"

**Solution**: Explicitly reference files:
```
Please read these files before starting:
1. .ai/prompts/developer_prompt.md
2. .ai/feature_list.md
3. .ai/architecture.md
```

#### "Agent forgets ADDS structure"

**Solution**: Include key reminders in each prompt:
```
Remember to:
1. Update feature_list.md status when done
2. Append to progress.md with session summary
3. Follow the testing requirements in the feature
```

#### "Tests fail in IDE but pass in terminal"

**Solution**: Check environment differences:
```bash
# Run in IDE terminal
which node
node --version
npm --version

# Compare with system terminal
```

---

## Recommended IDE Features

| Feature | Why It Helps ADDS |
|---------|-------------------|
| **Agent Mode** | Can follow complex multi-step instructions |
| **File Context** | Can read .ai/ configuration files |
| **Terminal Integration** | Can run init.sh and tests |
| **Diff View** | Review changes before applying |
| **Git Integration** | Commit changes with context |

---

## Migration Between IDEs

ADDS is IDE-agnostic. To switch:

1. **Copy your project** (all ADDS files are in `.ai/`)
2. **Open in new IDE**
3. **Reference same prompt files**
4. **Continue where you left off**

Your `feature_list.md`, `progress.md`, and `architecture.md` travel with you.
