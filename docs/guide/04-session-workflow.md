# Session Workflow

> Day-to-day operations for ADDS development

---

## Starting a Session

### 1. Determine Your Role

Use the [Agent Selection Guide](./03-agent-selection.md) to determine which agent to use.

### 2. Read the Prompt File

Open the appropriate prompt file:
```
.ai/prompts/{agent}_prompt.md
```

### 3. Read Context Files

Always read these files in order:
1. `CORE_GUIDELINES.md` - Quick reference
2. `.ai/feature_list.md` - Current state
3. `.ai/progress.md` - Recent history
4. `.ai/architecture.md` - Technical context (if relevant)

### 4. Execute

Follow the prompt instructions for your role.

---

## During the Session

### Developer Agent Workflow

```
1. Select ONE pending feature with all dependencies completed
2. Read feature details from feature_list.md
3. Implement the feature
4. Write/update tests
5. Run tests locally
6. Update feature status to "testing"
7. Append session summary to progress.md
```

### Tester Agent Workflow

```
1. Find features with status "testing"
2. Read test cases from feature_list.md
3. Run all tests for the feature
4. Run regression tests
5. Update feature status:
   - All pass → "completed"
   - Any fail → "bug"
6. Append test results to progress.md
```

---

## Ending a Session

### Required Updates

Always update these files before ending:

1. **feature_list.md** - Update feature status
2. **progress.md** - Append session summary
3. **session_log.jsonl** - Log session events (optional, via script)

### Session Summary Template

```markdown
## Session YYYY-MM-DD HH:MM - {Agent} Agent

**Feature**: F00X
**Status**: {old_status} → {new_status}

### Completed
- Task one
- Task two

### Issues
- Issue one (if any)

### Next Steps
- What the next agent should do
```

---

## Context Management

### When progress.md Gets Too Large

If `progress.md` exceeds 1000 lines, compress it:

```bash
python scripts/compress_context.py --project-dir .
```

This archives old sessions while keeping recent ones accessible.

### Logging Session Events

Record structured session data:

```bash
# Start session
python scripts/log_session.py --feature F001 --agent developer --action start

# Complete session
python scripts/log_session.py --feature F001 --agent developer --action complete --files-changed 5

# View stats
python scripts/log_session.py --stats
```

---

## Handoff Protocol

### From Developer to Tester

1. Developer completes implementation
2. Developer updates feature status to `testing`
3. Developer appends session summary to progress.md
4. **Handoff**: Next session starts with Tester Agent

### From Tester to Developer (Bug Found)

1. Tester runs tests, finds failures
2. Tester updates feature status to `bug`
3. Tester documents failures in progress.md
4. **Handoff**: Next session starts with Developer Agent to fix

### From Tester to Reviewer (All Pass)

1. Tester verifies all tests pass
2. Tester updates feature status to `completed`
3. Tester appends test results to progress.md
4. **Handoff**: When all features complete, use Reviewer Agent

---

## Troubleshooting

### "I don't know which agent to use"

Check `.ai/feature_list.md`:
- No file? → PM Agent
- No architecture? → Architect Agent
- Pending features? → Developer Agent
- Testing features? → Tester Agent
- All complete? → Reviewer Agent

### "The feature I want to work on has dependencies"

Wait until all dependencies show `completed` status. Work on independent features first.

### "Tests fail but I'm the Developer"

Fix the implementation. Don't hand off to Tester until tests pass locally.

### "I found a bug in a completed feature"

1. Update that feature's status to `regression`
2. Document in progress.md
3. Fix as Developer Agent

---

## Best Practices

1. **One feature per session** - Don't implement multiple features
2. **Update status immediately** - Don't wait until the end
3. **Write detailed progress** - Future agents need context
4. **Run tests before handoff** - Don't pass broken code
5. **Follow the prompt** - Each agent has specific instructions
