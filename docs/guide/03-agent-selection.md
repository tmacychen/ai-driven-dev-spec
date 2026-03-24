# Agent Selection Guide

> How to choose the right agent for each phase

---

## Decision Tree

```
IF feature_list.md does NOT exist
  → Use PM Agent (pm_prompt.md)
    Action: Read app_spec.md → Generate feature_list.md

ELSE IF architecture.md is empty or "TBD" everywhere
  → Use Architect Agent (architect_prompt.md)
    Action: Read feature_list.md → Design architecture → Create init.sh

ELSE IF any feature has status = "pending" and all dependencies are "completed"
  → Use Developer Agent (developer_prompt.md)
    Action: Select next pending feature → Implement → Set status to "testing"

ELSE IF any feature has status = "testing"
  → Use Tester Agent (tester_prompt.md)
    Action: Run tests → Verify acceptance criteria → Set status to "completed" or "bug"

ELSE IF all features are "completed" or "pending" (none "testing")
  → Use Reviewer Agent (reviewer_prompt.md)
    Action: Review recent commits → Security audit → Approve or reject

ELSE IF any feature has status = "blocked" or "regression"
  → Use Developer Agent (developer_prompt.md)
    Action: Fix blocker or regression → Re-test
```

---

## Agent Details

### PM Agent

**When to use**: Starting a new project, or feature_list.md is missing/outdated

**Input**: `app_spec.md` (original requirements)

**Output**: `.ai/feature_list.md`

**Key tasks**:
- Decompose requirements into 50-200 atomic features
- Assign priorities (high/medium/low)
- Define dependencies between features
- Create test cases for each feature

**Handoff condition**: feature_list.md created with at least one feature

---

### Architect Agent

**When to use**: After PM completes, before development starts

**Input**: `.ai/feature_list.md`

**Output**: `.ai/architecture.md`, `init.sh`

**Key tasks**:
- Design system architecture
- Select technology stack
- Define data models and APIs
- Create environment setup script (init.sh)

**Handoff condition**: architecture.md complete, init.sh runs successfully

---

### Developer Agent

**When to use**: Architecture ready, features pending

**Input**: `.ai/feature_list.md`, `.ai/architecture.md`

**Output**: Code, tests, updated feature_list.md status

**Key tasks**:
- Implement ONE feature per session
- Write unit tests
- Update feature status to `testing`
- Append session summary to progress.md

**Handoff condition**: Feature implemented, status set to `testing`

---

### Tester Agent

**When to use**: Feature status is `testing`

**Input**: `.ai/feature_list.md`, implementation

**Output**: Test results, updated feature_list.md status

**Key tasks**:
- Run all test cases for the feature
- Run regression tests (previous features)
- Verify acceptance criteria
- Set status to `completed` or `bug`

**Handoff condition**: Tests complete, status updated

---

### Reviewer Agent

**When to use**: All features `completed` or ready for release

**Input**: Code changes, `.ai/feature_list.md`

**Output**: Review report, approval/rejection

**Key tasks**:
- Review code quality
- Check security vulnerabilities
- Verify architecture compliance
- Ensure test coverage

**Handoff condition**: Review complete, decision made

---

## Quick Reference

| State | Agent | Action |
|-------|-------|--------|
| No feature_list.md | PM | Create feature list |
| No architecture | Architect | Design system |
| Pending features | Developer | Implement next feature |
| Testing features | Tester | Run tests |
| All completed | Reviewer | Final review |
| Blocked/Regression | Developer | Fix issues |

---

## Common Mistakes

### ❌ Wrong: Developer creates feature list
**Why**: PM Agent is optimized for requirements analysis and decomposition

### ❌ Wrong: Developer designs architecture while implementing
**Why**: Leads to inconsistent design decisions and technical debt

### ❌ Wrong: Tester finds bug but doesn't mark status
**Why**: Next agent won't know to fix it

### ✅ Right: Each agent completes their phase before handoff
**Why**: Clear boundaries prevent context confusion
