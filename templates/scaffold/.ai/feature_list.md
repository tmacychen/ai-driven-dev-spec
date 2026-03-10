# Feature List

> 项目功能跟踪表 - AI 开发的核心状态管理文件

## 状态说明

| 状态 | 含义 |
|------|------|
| `pending` | 待开发 |
| `in_progress` | 开发中 |
| `completed` | 已完成 |
| `blocked` | 已阻塞 |
| `regression` | 回归问题 |

---

## F001: Project initialization and environment setup

- **Category**: core
- **Priority**: high
- **Status**: pending
- **Dependencies**: -
- **Complexity**: low

### Steps
1. Create project directory structure
2. Setup build system and dependencies
3. Write init.sh for automation
4. Initial git commit

### Test Cases

| ID | Description | Type | Status |
|----|-------------|------|--------|
| T001-01 | init.sh runs successfully | integration | pending |

### Acceptance Criteria
- [ ] Project structure created
- [ ] Dependencies installed
- [ ] init.sh runs without errors

### Security Checks
- (none)

---

<!-- Template for new features:

## F00X: [Feature Description]

- **Category**: core/feature/fix/refactor/chore/test/docs
- **Priority**: high/medium/low
- **Status**: pending
- **Dependencies**: F00X, F00Y
- **Complexity**: low/medium/high

### Steps
1. Step 1
2. Step 2

### Test Cases

| ID | Description | Type | Status |
|----|-------------|------|--------|
| T00X-01 | Test description | unit/integration/e2e | pending |

### Acceptance Criteria
- [ ] Criterion 1
- [ ] Criterion 2

### Security Checks
- Check 1 (if applicable)

-->
