# ADDS v2.0 Quick Start Guide

**Get started in 5 minutes**

---

## Overview

ADDS v2.0 is an AI-driven development specification that enables AI Agents to autonomously complete project development through **architectural constraints rather than AI understanding**.

### Core Philosophy

```
v1.0: Trust AI to understand specifications → Uncertainty
v2.0: Architectural constraints enforce behavior → Certainty ✅
```

---

## 5-Step Quick Start

### Step 1: Initialize Project (1 minute)

```bash
cd your-project
python3 /path/to/scripts_v2/adds_v2.py init
```

This creates:
```
your-project/
├── .ai/
│   ├── feature_list.md    # Feature tracking
│   ├── progress.md        # Session history
│   └── prompts/           # System prompts
└── app_spec.md           # Your requirements
```

### Step 2: Edit Requirements (2 minutes)

Edit `app_spec.md` to describe what you want to build:

```markdown
# My Project

## Core Features
- User authentication with JWT
- REST API for CRUD operations
- Real-time notifications

## Technical Stack
- Backend: Python FastAPI
- Database: PostgreSQL
- Cache: Redis
```

### Step 3: View Recommended Agent (30 seconds)

```bash
python3 scripts_v2/adds_v2.py route
```

Output:
```
📍 Recommended Agent: PM Agent
   Reason: feature_list.md does not exist
   Next Step: Run PM Agent to create feature list
```

### Step 4: Start Development Loop (1 minute)

```bash
python3 scripts_v2/adds_v2.py start --max-turns 10
```

The Agent Loop will:
1. Auto-inject system prompt with ADDS constraints
2. Select appropriate agent (PM/Developer/Tester/Reviewer)
3. Execute agent with latch protection
4. Track compliance in real-time

### Step 5: Check Progress (30 seconds)

```bash
python3 scripts_v2/adds_v2.py status
```

Output:
```
📊 ADDS Project Status
──────────────────────────────────────────
  Total:       25
  Pending:     15
  In Progress: 2
  Testing:     3
  Completed:   5

  Progress: [██████████░░░░░░░░░░░░░░░░░░░░] 20%  (5/25)

🔒 Latch Status:
  Project Latch: PM (locked)
  Feature Latch: F003 (locked)

📈 Compliance Score: 0.92
```

---

## Core Features

### 1. Segmented System Prompt

```python
# Static section (globally cacheable)
[IDENTITY]
You are an AI Agent following ADDS specification...

[CORE_PRINCIPLES]
- One feature at a time
- State-driven execution
- Fail-closed design

# Boundary marker
STATIC_BOUNDARY

# Dynamic section (generated on demand)
[STATE_MANAGEMENT]
Current project: my-project
Pending features: 15
Current agent: Developer Agent

[FEATURE_WORKFLOW]
Next feature: F004 - User Authentication
Dependencies: F001, F002 (completed)
```

**Advantages**:
- Static section can be globally cached (save token costs)
- Dynamic section adapts to project state
- Clear boundary for management

### 2. Agent Loop State Machine

```python
async def adds_loop(initial_state):
    while True:
        # 1. Context preprocessing
        context = await preprocess_context()
        
        # 2. Route to appropriate agent
        agent = route_agent(context)
        
        # 3. Execute with latch protection
        result = await execute_agent(agent, context)
        
        # 4. Update state with lock
        update_state(result)
        
        # 5. Check termination
        if should_terminate(result):
            break
```

**Advantages**:
- State-driven, not AI judgment
- Prevents illegal state transitions
- Latch mechanism prevents state thrashing

### 3. Fail-Closed Mechanism

```python
class SafetyDefaults:
    @staticmethod
    def safe_feature_selection(features):
        pending = [f for f in features if f.status == 'pending']
        
        if not pending:
            # Fail-closed: stop rather than guess
            raise RuntimeError("No pending features - stopping")
        
        # Deterministic selection
        return pending[0]
```

**Advantages**:
- Default to safest behavior
- Avoid error accumulation
- Explicit declaration required for dangerous operations

### 4. Compliance Tracking

```python
tracker = ComplianceTracker()

# Check one-feature-per-session
tracker.check_one_feature_per_session(feature_name)

# Check valid status transition
tracker.check_valid_status_transition(old_status, new_status)

# Check agent boundary
tracker.check_agent_boundary(agent, operation)

# Get compliance score
score = tracker.get_compliance_score()  # 0.0 - 1.0
```

**Advantages**:
- Proactive violation detection
- Evidence recording for debugging
- Quantified compliance score

---

## Agent Roles

### PM Agent
- **Responsibility**: Analyze requirements, decompose tasks
- **Triggers**: `feature_list.md` does not exist
- **Outputs**: Feature list with 50-200 atomic items

### Architect Agent
- **Responsibility**: Design system architecture
- **Triggers**: `architecture.md` is empty
- **Outputs**: Architecture decisions, tech stack selection

### Developer Agent
- **Responsibility**: Implement features one at a time
- **Triggers**: Pending features with dependencies met
- **Outputs**: Implementation + unit tests

### Tester Agent
- **Responsibility**: Run tests, verify features
- **Triggers**: Features in `testing` status
- **Outputs**: Test results, status updates

### Reviewer Agent
- **Responsibility**: Code review, security audit
- **Triggers**: All features completed
- **Outputs**: Review report, recommendations

---

## Feature Lifecycle

```
pending → in_progress → testing → completed
                            ↓
                          bug → in_progress (fix cycle)
```

### Status Definitions

| Status | Meaning | Next Status |
|--------|---------|-------------|
| `pending` | Not started | `in_progress` |
| `in_progress` | Being implemented | `testing`, `blocked` |
| `testing` | Ready for testing | `completed`, `bug` |
| `completed` | Verified working | - |
| `bug` | Tests failed | `in_progress` |
| `blocked` | Dependencies not met | `in_progress` |

---

## Command Reference

```bash
# Project management
python3 scripts_v2/adds_v2.py init      # Initialize project
python3 scripts_v2/adds_v2.py status    # Show progress
python3 scripts_v2/adds_v2.py validate  # Validate feature_list.md
python3 scripts_v2/adds_v2.py route     # Recommend agent

# Development loop
python3 scripts_v2/adds_v2.py start     # Start Agent Loop
python3 scripts_v2/adds_v2.py stop      # Stop loop

# Testing
python3 scripts_v2/test_integration.py  # Run all tests (28 tests)
```

---

## Best Practices

### 1. Always Check Route First

```bash
python3 scripts_v2/adds_v2.py route
```

This tells you which agent is appropriate for the current state.

### 2. Use Latches for Stability

```python
# Latches prevent state thrashing within a session
project_latch = ProjectLatch(project_name="my-project")
project_latch.lock(agent="Developer")  # Lock to Developer Agent
```

### 3. Monitor Compliance Score

```bash
# Check compliance score (0.0 - 1.0)
python3 scripts_v2/adds_v2.py status
```

Score < 0.7 indicates violations.

### 4. Run Tests Regularly

```bash
# Run integration tests to verify functionality
python3 scripts_v2/test_integration.py
```

---

## Troubleshooting

### Problem: "No pending features"

**Cause**: All features completed or dependencies not met.

**Solution**:
```bash
# Check which features are blocked
python3 scripts_v2/adds_v2.py status

# View dependency graph
python3 scripts_v2/adds_v2.py dag
```

### Problem: "Invalid status transition"

**Cause**: Illegal state transition (e.g., `pending` → `completed`).

**Solution**: Follow the feature lifecycle:
```
pending → in_progress → testing → completed
```

### Problem: "Compliance score too low"

**Cause**: Violations detected (e.g., multiple features in one session).

**Solution**:
```bash
# View violations
python3 scripts_v2/adds_v2.py status

# Fix violations and restart
python3 scripts_v2/adds_v2.py start
```

---

## Next Steps

1. ✅ **Initialize your project** - `python3 scripts_v2/adds_v2.py init`
2. ✅ **Edit requirements** - Edit `app_spec.md`
3. ✅ **Start development** - `python3 scripts_v2/adds_v2.py start`
4. ✅ **Monitor progress** - `python3 scripts_v2/adds_v2.py status`

---

## Additional Resources

- **Usage Examples**: [v2-usage-examples.md](v2-usage-examples.md)
- **Detailed Comparison**: [v1-vs-v2-comparison.md](v1-vs-v2-comparison.md)
- **Improvement Plan**: [improvement-plan-summary.md](improvement-plan-summary.md)

---

**Ready to start? Just run:**

```bash
python3 scripts_v2/adds_v2.py init
```

🚀
