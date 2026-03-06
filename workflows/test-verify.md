---
description: Test and verification workflow
---

# Test & Verify Workflow

// turbo-all

## When to Execute

- After each feature implementation is completed
- At the start of each session (regression testing)
- Before code merging

## Steps

1. **Load Testing Guide**: Read `templates/prompts/testing_prompt.md` to understand verification standards.

2. **Identify Test Type**:
   - Web project → E2E testing priority (Playwright/Cypress)
   - API project → Integration testing (pytest/Jest)
   - CLI project → Command line output testing

3. **Execute Feature Tests**:
   ```bash
   # Run test cases for current feature
   npm test -- --grep "feature-name"
   # or
   pytest tests/test_feature.py -v
   ```

4. **Collect Evidence**:
   - Copy test output to terminal
   - Confirm all assertions show PASS
   - If E2E tests, confirm page behavior meets expectations

5. **Regression Testing** (at session start):
   - Filter `core: true` and `passes: true` features from `.ai/feature_list.json`
   - Run their `test_cases`
   - If any fail, follow regression handling process

6. **Update Test Status**:
   - Update each `test_cases[].status` in `.ai/feature_list.json`
   - `"passed"` | `"failed"` | `"pending"`

7. **Quality Review**:
   ```bash
   # Lint check
   npm run lint    # or flake8, eslint, etc.
   
   # Type check (if applicable)
   npx tsc --noEmit    # TypeScript
   mypy src/            # Python
   ```

8. **Output Verification Report**:
   ```
   ## 🧪 Test Report
   
   ### Feature: [Feature ID] - [Description]
   - test-001: ✅ PASSED
   - test-002: ✅ PASSED
   - test-003: ❌ FAILED (Reason: ...)
   
   ### Quality Check
   - Lint: ✅ 0 errors
   - Type Check: ✅ passed
   
   ### Summary
   X/Y tests passed
   ```