# .ai/archive/

This directory stores archived features that have been completed and removed from the active `feature_list.md`.

## Purpose

- Reduces `feature_list.md` size as the project grows
- Preserves full feature history for reference
- Each file is named after the feature ID (e.g., `F001.md`)

## Usage

Archive a completed feature with the ADDS CLI:

```bash
# Verify the feature is completed
adds status

# Archive it
adds archive F001
```

This will:
1. Copy the full feature section to `.ai/archive/F001.md`
2. Remove the feature from `feature_list.md`
3. Preserve all metadata, steps, test cases, and acceptance criteria

## File Format

Each archived file looks like:

```markdown
# Archived Feature

**Archived**: 2026-03-24T07:30:00+00:00

---

## F001: Project initialization and environment setup

- **Category**: core
- **Priority**: high
- **Status**: completed
...
```

## Restoring an Archived Feature

If you need to restore a feature (e.g., regression):

1. Copy the feature section from the archive file
2. Paste it back into `feature_list.md`
3. Update the status to `regression`
4. Delete the archive file
5. Run `adds validate` to confirm

## When to Archive

Archive features when:
- Status is `completed` ✓
- All test cases have passed ✓
- Code has been reviewed ✓
- Feature is no longer needed in the active list

Do NOT archive:
- `blocked` or `in_progress` features
- Features with incomplete dependencies
- Features that may still need modification
