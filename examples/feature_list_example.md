# Feature List Example

> 已填充的功能列表示例，展示完成状态

---

## F001: Project initialization and environment setup

- **Category**: core
- **Priority**: high
- **Status**: completed
- **Dependencies**: -
- **Complexity**: low

### Steps
1. Create project directory structure
2. Setup build system and dependencies
3. Write init.sh for automation
4. Run init.sh and verify output
5. Initial git commit

### Test Cases

| ID | Description | Type | Status |
|----|-------------|------|--------|
| T001-01 | init.sh runs without errors | integration | passed |
| T001-02 | Project structure is correct | unit | passed |

### Acceptance Criteria
- [x] Project structure matches architecture.md
- [x] init.sh bootstraps environment successfully
- [x] All core dependencies installed

### Security Checks
- (none)

---

## F002: Implement basic user login with hardcoded credentials

- **Category**: auth
- **Core**: true
- **Priority**: high
- **Status**: pending
- **Dependencies**: F001
- **Complexity**: medium

### Steps
1. Create login UI component
2. Implement POST /api/login endpoint
3. Verify 'Invalid Credentials' error on wrong login
4. Verify redirection to dashboard on correct login

### Test Cases

| ID | Description | Type | Status |
|----|-------------|------|--------|
| T002-01 | Successful login flow (E2E) | e2e | pending |
| T002-02 | Failed login shows error | e2e | pending |
| T002-03 | Login API responds correctly | integration | pending |

### Acceptance Criteria
- [ ] User can login with correct credentials
- [ ] User sees error with wrong credentials
- [ ] Login redirects to dashboard

### Security Checks
- Password must not be logged in plaintext
- Token must have expiration time
- Rate limiting on login endpoint

---

## F003: Main Dashboard layout with sidebar navigation

- **Category**: ui
- **Priority**: medium
- **Status**: pending
- **Dependencies**: F002
- **Complexity**: medium

### Steps
1. Create Layout component with children nesting
2. Add Sidebar items corresponding to app routes
3. Verify responsive menu behavior on mobile view

### Test Cases

| ID | Description | Type | Status |
|----|-------------|------|--------|
| T003-01 | Dashboard renders with sidebar | e2e | pending |
| T003-02 | Responsive sidebar collapses on mobile | e2e | pending |

### Acceptance Criteria
- [ ] Dashboard layout renders correctly
- [ ] Sidebar navigation works
- [ ] Responsive on mobile devices

### Security Checks
- (none)
