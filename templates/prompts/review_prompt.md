# ROLE: Code Review Agent

Use this checklist before marking any feature as complete.

## Pre-Commit Review Checklist

### 1. Functional Correctness
- [ ] All `acceptance_criteria` from `feature_list.json` are met
- [ ] All `test_cases` pass with tool-based evidence
- [ ] Edge cases are handled (empty inputs, boundary values, nulls)
- [ ] Error messages are clear and helpful

### 2. Code Quality
- [ ] Code follows project conventions (naming, structure, formatting)
- [ ] No TODO/FIXME/HACK comments left without tracking IDs
- [ ] Functions/methods are focused and reasonably sized
- [ ] No dead code or unused imports
- [ ] Lint passes with zero errors

### 3. Security (`security_checks`)
- [ ] All items in the feature's `security_checks` array are addressed
- [ ] User input is validated and sanitized
- [ ] No secrets or credentials hardcoded
- [ ] Sensitive data is not logged in plaintext
- [ ] Authentication/authorization checks are in place (if applicable)

### 4. Testing
- [ ] Unit tests cover core logic
- [ ] Integration tests cover data flow
- [ ] E2E tests cover user-facing behavior (Web projects)
- [ ] Tests are deterministic (no flaky tests)
- [ ] Test coverage meets project minimum (≥ 70%)

### 5. Documentation
- [ ] README updated if public API changed
- [ ] Code comments explain "why", not "what"
- [ ] API documentation updated (if applicable)
- [ ] `.ai/architecture.md` updated if design decisions changed

### 6. Git Hygiene
- [ ] Single feature per commit
- [ ] Commit message follows convention: `feat(<scope>): desc [Closes #ID]`
- [ ] No build artifacts or dependency folders committed
- [ ] `.gitignore` is up to date

### 7. State Management
- [ ] `.ai/feature_list.json` updated:
  - `passes: true`
  - `status: "completed"`
  - `last_worked_on` set
  - All `test_cases[].status` updated
- [ ] `.ai/progress.md` updated with session summary and handoff notes

## Review Outcome

After completing the checklist:
- ✅ **All checks pass** → Commit and proceed.
- ⚠️ **Minor issues** → Fix before committing, document decisions.
- ❌ **Major issues** → Do not commit. Fix the issues first.
