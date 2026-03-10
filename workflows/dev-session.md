---
description: Single AI incremental development session workflow (including security and regression checks)
---

# Development Session Workflow

// turbo-all

## Phase 1: Environment and Stability (Must execute first)

1. Run `bash init.sh` to ensure environment is ready, dependencies are installed, and services are started.
2. Read `CORE_GUIDELINES.md` to align role, read `progress.log` and `.ai/feature_list.md` to get latest context.
3. Run `git log --oneline -5` to check recent changes.
4. **Regression Check**: Select 1-2 core features from completed features and run their `test_cases`.
   - If all pass → continue.
   - If any fail → **Fix immediately**, mark as `regression`, record in progress.md.

## Phase 2: Task Selection and Development

5. Load `templates/prompts/coding_prompt.md` as system prompt.
6. **Task Selection**: Find first eligible task in `.ai/feature_list.md`:
   - status: `pending`
   - All `dependencies` completed
   - Sorted by `priority` (high > medium > low)
7. Update the feature's `status` to `"in_progress"`.

## Phase 3: Implementation and Verification

8. **Write code**: Only for the selected feature.
9. **Verify implementation**:
   - Execute all `test_cases`.
10. **Collect evidence**: Obtain logs, screenshots, or API responses.
11. **Handle failures (Retry)**:
    - If tests fail, classify by error type and attempt to fix.
    - Increase `retry_count`.
    - If `max_retries` is reached, execute `git reset --hard`, mark as `blocked` and skip.
12. **Security and review**: Verify `security_checks` are handled, self-check against `review_prompt.md`.

## Phase 4: Persistence and Handoff

13. Git commit.
14. Update `.ai/feature_list.md`:
    - status: `completed`
15. Update `progress.log`:
    - **Append** human-readable summary of this session, verification evidence, handoff instructions.
    - Update top-level statistics.
16. Output session summary report.