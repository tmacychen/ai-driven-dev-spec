# Feature Branch Workflow

> Parallel development strategy for ADDS projects

---

## Overview

When multiple developers or AI Agents work on the same project simultaneously, a feature branch workflow prevents conflicts and enables parallel development.

---

## Branch Naming Convention

```
feature/F001-short-description
bugfix/F003-fix-auth-error
refactor/F005-extract-service
```

---

## Workflow

### 1. Starting a New Feature

```bash
# Ensure you're on main and up to date
git checkout main
git pull origin main

# Create feature branch
git checkout -b feature/F001-user-authentication

# Update feature status in feature_list.md
# Change F001 status from "pending" to "in_progress"
```

### 2. During Development

```bash
# Regular commits
git add .
git commit -m "feat(F001): implement user login"

# Push branch to remote
git push -u origin feature/F001-user-authentication
```

### 3. Before Merging

```bash
# Update from main
git fetch origin
git rebase origin/main

# Resolve any conflicts

# Run tests
./init.sh && npm test
```

### 4. Merging

```bash
# Merge to main
git checkout main
git merge --no-ff feature/F001-user-authentication

# Update feature status
git add .ai/feature_list.md
git commit -m "complete(F001): mark as completed"

# Push
git push origin main

# Delete branch (optional)
git branch -d feature/F001-user-authentication
git push origin --delete feature/F001-user-authentication
```

---

## ADDS-Specific Considerations

### Feature List Synchronization

When working in parallel, feature dependencies become critical:

```markdown
## F002: User Profile

- **Status**: pending
- **Dependencies**: F001  ← Wait for F001 to complete
```

**Rule**: Never start a feature until all dependencies are merged to `main`.

### Progress.md Handling

Each branch maintains its own progress entries:

```markdown
## Session 2026-03-24 10:00 - Developer Agent (feature/F001)

**Branch**: feature/F001-user-authentication
**Feature**: F001
**Status**: in_progress

### Completed
- Implemented login form
```

When merging, progress entries are preserved.

### Architecture Changes

If a feature requires architecture changes:

1. Document changes in `.ai/architecture.md` on the branch
2. Review with Architect Agent before merging
3. Update `init.sh` if new setup steps are needed

---

## Conflict Resolution

### Feature List Conflicts

When two branches modify `feature_list.md`:

```bash
# During rebase/merge, you'll see conflicts like:
<<<<<<< HEAD
- **Status**: completed
=======
- **Status**: testing
>>>>>>> feature/F002
```

**Resolution**:
- Keep the most advanced status
- If unsure, mark as `in_progress` and re-test

### Progress.md Conflicts

Progress.md is append-only, so conflicts are rare. If they occur:

1. Keep both entries
2. Ensure chronological order

### Code Conflicts

Resolve as normal, then:

```bash
# Re-run tests
npm test

# Update feature status if needed
# Mark as "testing" if unsure
```

---

## Multi-Agent Coordination

### Scenario: Two Agents on Different Features

```
Agent A: Working on F001 (authentication)
Agent B: Working on F004 (dashboard)

Both features are independent (no dependencies)
```

**Workflow**:
1. Agent A creates `feature/F001`
2. Agent B creates `feature/F004`
3. Both work independently
4. Agent A merges first (F001 completed)
5. Agent B rebases, then merges

### Scenario: Dependent Features

```
Agent A: Working on F001 (authentication) - BLOCKER
Agent B: Waiting for F001 to start F002 (profile)
```

**Workflow**:
1. Agent A works on F001
2. Agent B prepares architecture/docs for F002
3. Agent A merges F001
4. Agent B pulls main, starts F002

---

## Best Practices

### ✅ DO

- Create branches early (when starting a feature)
- Push branches regularly (backup)
- Rebase from main before merging
- Run full test suite before merging
- Update feature_list.md status on branch

### ❌ DON'T

- Work directly on `main`
- Start features with incomplete dependencies
- Force push to shared branches
- Merge without testing
- Delete branches before confirming merge

---

## Automation Ideas

### Pre-commit Hook

```bash
#!/bin/bash
# .git/hooks/pre-commit

# Validate feature_list.md
python scripts/validate_feature_list.py --project-dir .

# Check for forbidden commands
if git diff --cached | grep -E "(sudo|rm -rf /)"; then
    echo "❌ Forbidden commands detected"
    exit 1
fi
```

### Post-merge Hook

```bash
#!/bin/bash
# .git/hooks/post-merge

# Check if feature_list.md was modified
if git diff HEAD@{1} HEAD --name-only | grep -q "feature_list.md"; then
    echo "📋 Feature list updated"
    python scripts/validate_feature_list.py --project-dir .
fi
```

---

## Troubleshooting

### "Feature branch is behind main"

```bash
git fetch origin
git rebase origin/main
# Resolve conflicts if any
```

### "Can't merge, tests fail"

```bash
# On your branch
git rebase origin/main
# Fix issues
npm test
# Commit fixes
git push --force-with-lease
```

### "Feature list has conflicts"

1. Open `feature_list.md`
2. Find conflict markers
3. Choose correct status (usually the more advanced one)
4. Commit resolution

---

## Summary

| Situation | Action |
|-----------|--------|
| Starting feature | Create branch `feature/F###` |
| Dependencies incomplete | Wait, prepare docs |
| Ready to merge | Rebase, test, merge |
| Conflict in feature_list.md | Keep advanced status |
| Tests fail after merge | Fix on branch, re-merge |
