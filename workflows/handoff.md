---
description: Project session handoff specification process (including security and stability verification)
---

# Handoff Workflow

After completing an incremental feature, the AI Agent must execute this process to ensure a smooth handoff to the new context window.

## Handoff Checklist

### 1. Code Commit
- [ ] All code changes have been committed via `git add . && git commit`.
- [ ] Commit message format is correct: `feat(<scope>): desc [Closes #ID]`.
- [ ] No untracked key files.

### 2. Status Synchronization
- [ ] `.ai/feature_list.json` has been updated.
- [ ] `progress.log` has been updated:
  - Updated the top "Overall Status".
  - **Appended** human-readable history for this session.
  - "Current Focus" points to the next feature to be developed.

### 3. Handoff Instructions
Clearly list in `progress.log`:
- ✅ What was completed in this session
- 🎯 Which task should start next
- ⚠️ Any known unfixed bugs or technical debt
- 💡 Any key design decisions or context information

### 4. Environment Cleanup
- [ ] Ensure no hanging background processes (e.g., unclosed dev server).
- [ ] If there are temporary files, they have been cleaned up.

### 5. Handoff Verification
- [ ] Run `bash init.sh` to confirm the project still passes self-check in a "clean" state.
- [ ] Run tests for 1 core feature to confirm system stability.
- [ ] Confirm the basic entry point for the next session in `progress.log`.

### 6. Session Archiving (Optional)
If there are important thought processes or design decisions, append to `.ai/session_log.jsonl`:

```json
{"timestamp": "2026-02-26T14:00:00Z", "session": 5, "feature": "F012", "action": "completed", "notes": "Chose SQLite over PostgreSQL for simplicity in dev phase", "next": "F013"}
```