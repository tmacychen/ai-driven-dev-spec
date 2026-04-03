# ADDS Usage Examples & Best Practices

**Real-world scenarios and practical guidance**

---

## Quick Navigation

- [Scenario 1: Web API Project](#scenario-1-web-api-project)
- [Scenario 2: CLI Tool Development](#scenario-2-cli-tool-development)
- [Scenario 3: Data Pipeline](#scenario-3-data-pipeline)
- [Scenario 4: Library Package](#scenario-4-library-package)
- [Best Practices](#best-practices)
- [Troubleshooting](#troubleshooting)

---

## Scenario 1: Web API Project

### Project Setup

```bash
# Create project directory
mkdir my-api && cd my-api

# Initialize ADDS
python3 /path/to/scripts/adds.py init

# Edit requirements
cat > app_spec.md << 'EOF'
# Task Management API

## Core Features
- User authentication with JWT
- Task CRUD operations
- Task assignment and tracking
- Real-time notifications

## Technical Stack
- Backend: Python FastAPI
- Database: PostgreSQL
- Cache: Redis
- Message Queue: Celery

## Non-Functional Requirements
- API response time < 200ms
- Support 1000 concurrent users
- 99.9% uptime SLA
EOF
```

### Development Workflow

#### Session 1: PM Agent (Requirements Analysis)

```bash
# Check route
python3 scripts/adds.py route
# Output: Recommend PM Agent

# Start development
python3 scripts/adds.py start --max-turns 10

# PM Agent will:
# 1. Analyze app_spec.md
# 2. Decompose into 80+ features
# 3. Create feature_list.md
# 4. Lock latch to PM Agent
```

**Feature List Generated** (excerpt):
```markdown
## F001: User Registration

- **Category**: feature
- **Priority**: high
- **Complexity**: medium
- **Status**: pending
- **Dependencies**: -

Acceptance Criteria:
- POST /api/auth/register endpoint
- Email validation
- Password hashing with bcrypt
- JWT token generation

## F002: User Login

- **Category**: feature
- **Priority**: high
- **Complexity**: low
- **Status**: pending
- **Dependencies**: F001

Acceptance Criteria:
- POST /api/auth/login endpoint
- JWT token validation
- Refresh token support
```

#### Session 2: Architect Agent (System Design)

```bash
# Check route
python3 scripts/adds.py route
# Output: Recommend Architect Agent

# Architect Agent will:
# 1. Design system architecture
# 2. Select tech stack components
# 3. Create architecture.md
```

**Architecture Document**:
```markdown
# System Architecture

## High-Level Design
- Layered architecture (Controller → Service → Repository)
- RESTful API design
- Event-driven notifications

## Tech Stack Details
- FastAPI with async/await
- SQLAlchemy ORM
- Alembic for migrations
- Pydantic for validation

## Database Schema
- Users table
- Tasks table
- Assignments table
- Notifications table
```

#### Session 3-25: Developer Agent (Feature Implementation)

```bash
# Start feature implementation
python3 scripts/adds.py start

# Developer Agent will:
# 1. Select F001 (User Registration)
# 2. Lock latch to F001
# 3. Implement feature
# 4. Write unit tests
# 5. Update status: pending → testing
```

**Implementation Process**:

```
Iteration 1: Select F001 (highest priority, no dependencies)
  ↓
Latch: F001 locked for this session
  ↓
Implement:
  - Create models/user.py
  - Create api/auth.py
  - Create services/auth_service.py
  - Write tests/test_auth.py
  ↓
Update status: F001 → testing
  ↓
Session complete (latch released)
```

#### Session 26: Tester Agent (Verification)

```bash
# Check route
python3 scripts/adds.py route
# Output: Recommend Tester Agent (features in testing)

# Tester Agent will:
# 1. Run tests for F001
# 2. Verify acceptance criteria
# 3. Update status: testing → completed
```

#### Session 27+: Continue Development

```bash
# Developer Agent continues with F002
python3 scripts/adds.py start

# Latch prevents switching to F003 within same session
```

### Compliance Monitoring

```bash
# Check compliance score
python3 scripts/adds.py status

# Output:
📊 ADDS Project Status
──────────────────────────────────────────
  Total:       80
  Pending:     45
  In Progress: 1
  Testing:     5
  Completed:   29

  Progress: [██████████░░░░░░░░░░░░░░░░░░░░] 36%  (29/80)

🔒 Latch Status:
  Project Latch: Developer (locked)
  Feature Latch: F003 (locked)

📈 Compliance Score: 0.94

✅ All constraints followed
✅ One feature per session
✅ Valid status transitions
```

---

## Scenario 2: CLI Tool Development

### Project Setup

```bash
mkdir my-cli && cd my-cli

python3 /path/to/scripts/adds.py init

cat > app_spec.md << 'EOF'
# Data Processing CLI

## Core Features
- Parse CSV/JSON/YAML files
- Transform and validate data
- Generate reports
- Export to multiple formats

## Technical Stack
- CLI Framework: Click
- Data Processing: Pandas
- Validation: Pydantic
- Testing: pytest
EOF
```

### Development Workflow

```bash
# Session 1: PM Agent creates 30 features
python3 scripts/adds.py start

# Session 2: Architect Agent designs CLI structure
python3 scripts/adds.py start

# Session 3+: Developer Agent implements features
python3 scripts/adds.py start

# After all features complete: Reviewer Agent
python3 scripts/adds.py route
# Output: Recommend Reviewer Agent
```

### Feature Example: CSV Parser

```python
# F001: CSV Parser Implementation

# Developer Agent implements:
# src/parsers/csv_parser.py
import pandas as pd
from typing import List, Dict
from pydantic import BaseModel

class CSVParser:
    def __init__(self, file_path: str):
        self.file_path = file_path
        self.data = None
    
    def parse(self) -> List[Dict]:
        """Parse CSV file to list of dicts"""
        self.data = pd.read_csv(self.file_path)
        return self.data.to_dict('records')
    
    def validate(self, schema: BaseModel) -> bool:
        """Validate data against schema"""
        for row in self.data.to_dict('records'):
            schema(**row)
        return True

# tests/test_csv_parser.py
def test_csv_parser():
    parser = CSVParser('tests/data/sample.csv')
    data = parser.parse()
    assert len(data) > 0
    assert isinstance(data, list)
```

---

## Scenario 3: Data Pipeline

### Project Setup

```bash
mkdir data-pipeline && cd data-pipeline

python3 /path/to/scripts/adds.py init

cat > app_spec.md << 'EOF'
# ETL Data Pipeline

## Core Features
- Extract data from multiple sources (API, DB, Files)
- Transform and clean data
- Load to data warehouse
- Schedule and monitor jobs

## Technical Stack
- Orchestration: Apache Airflow
- Processing: Apache Spark
- Storage: PostgreSQL + S3
- Monitoring: Prometheus + Grafana
EOF
```

### Key Difference: Complex Dependencies

```markdown
## F001: API Data Extractor

- **Status**: pending
- **Dependencies**: -

## F002: Database Data Extractor

- **Status**: pending
- **Dependencies**: -

## F003: Data Transformation Engine

- **Status**: pending
- **Dependencies**: F001, F002  # Needs both extractors

## F004: Data Quality Validator

- **Status**: pending
- **Dependencies**: F003  # Needs transformation

## F005: Data Warehouse Loader

- **Status**: pending
- **Dependencies**: F003, F004  # Needs transformation and validation
```

**ADDS automatically respects dependencies**:
```bash
python3 scripts/adds.py next
# Output: F001 (no dependencies, highest priority)

# After F001 completed:
python3 scripts/adds.py next
# Output: F002 (no dependencies, second highest priority)

# After F001 and F002 completed:
python3 scripts/adds.py next
# Output: F003 (dependencies F001, F002 met)
```

---

## Scenario 4: Library Package

### Project Setup

```bash
mkdir my-lib && cd my-lib

python3 /path/to/scripts/adds.py init

cat > app_spec.md << 'EOF'
# Date Utility Library

## Core Features
- Date parsing and formatting
- Timezone handling
- Date arithmetic
- Natural language date processing

## Technical Stack
- Python 3.9+
- Type hints throughout
- Comprehensive docstrings
- 100% test coverage

## Distribution
- PyPI package
- Documentation on ReadTheDocs
EOF
```

### Special Considerations: Public API Design

```bash
# PM Agent creates features with API stability in mind

## F001: Core Date Parser

- **Category**: core
- **Priority**: critical
- **Complexity**: high
- **Status**: pending
- **Dependencies**: -

Acceptance Criteria:
- Parse ISO 8601 dates
- Parse common formats (YYYY-MM-DD, MM/DD/YYYY)
- Handle timezone-aware dates
- Public API: DateParser class
- Stability: SemVer guarantee
```

---

## Best Practices

### 1. Always Check Route First

```bash
# Before starting any session
python3 scripts/adds.py route
```

**Why**: Ensures you use the right agent for the current state.

**Example**:
```
📍 Recommended Agent: Developer Agent
   Reason: Pending features with dependencies met
   Next Feature: F003 - User Authentication
```

### 2. Monitor Compliance Score

```bash
# Check compliance after each session
python3 scripts/adds.py status
```

**Good Score**: ≥ 0.8
**Acceptable**: 0.7 - 0.8
**Needs Attention**: < 0.7

**What to do if score is low**:
```bash
# View violations
cat .ai/progress.md | grep "VIOLATION"

# Fix violations in next session
python3 scripts/adds.py start
```

### 3. Use Latches Correctly

**Latch Behavior**:
```python
# Latch is locked at session start
project_latch.lock(agent="Developer", feature="F003")

# During session: cannot switch features
if latches.is_locked():
    # All operations must target F003
    pass

# Latch is released at session end
project_latch.release()
```

**Common Mistake**:
```bash
# ❌ Wrong: Try to work on F004 in same session
python3 scripts/adds.py start --feature F004
# Error: Latch is locked to F003
```

### 4. Write Good Feature Descriptions

**Bad Example**:
```markdown
## F001: User Auth

- **Status**: pending

Implement user authentication.
```

**Good Example**:
```markdown
## F001: User Registration with Email Verification

- **Category**: feature
- **Priority**: high
- **Complexity**: medium
- **Status**: pending
- **Dependencies**: -

Acceptance Criteria:
- POST /api/auth/register endpoint
- Email format validation
- Password strength validation (min 8 chars, 1 number, 1 special char)
- Password hashing with bcrypt (cost factor 12)
- Send verification email
- JWT token generation (RS256, 24h expiry)
- Unit tests: ≥90% coverage
- Integration tests: happy path + error cases
```

### 5. Follow Feature Lifecycle

```
pending → in_progress → testing → completed
                            ↓
                          bug → in_progress (fix cycle)
```

**Valid Transitions**:
- `pending` → `in_progress` (Developer starts work)
- `in_progress` → `testing` (Developer finishes implementation)
- `testing` → `completed` (Tester verifies)
- `testing` → `bug` (Tester finds issue)
- `bug` → `in_progress` (Developer fixes)

**Invalid Transitions** (will be blocked):
- `pending` → `completed` (skip testing)
- `in_progress` → `completed` (skip testing)
- `completed` → `in_progress` (regression)

### 6. Use Evidence-Based Status Updates

**Bad**:
```markdown
## F001: User Registration

- **Status**: completed
```

**Good**:
```markdown
## F001: User Registration

- **Status**: completed
- **Evidence**:
  - Unit tests: 15/15 passing
  - Integration tests: 8/8 passing
  - Coverage: 94%
  - Manual test: ✅ Verified
  - API docs: ✅ Updated
```

---

## Troubleshooting

### Problem: "No pending features found"

**Symptom**:
```bash
python3 scripts/adds.py next
# Error: No pending features
```

**Diagnosis**:
```bash
# Check status
python3 scripts/adds.py status

# Check for blocked features
python3 scripts/adds.py validate
```

**Possible Causes**:
1. All features completed
2. All pending features have unmet dependencies
3. feature_list.md is corrupted

**Solutions**:
```bash
# Case 1: All completed → start review
python3 scripts/adds.py route
# Output: Recommend Reviewer Agent

# Case 2: Blocked dependencies → check DAG
python3 scripts/adds.py dag
# Identify which dependencies are blocking

# Case 3: Corrupted file → re-validate
python3 scripts/adds.py validate --fix
```

### Problem: "Invalid status transition"

**Symptom**:
```
Error: Cannot transition from 'pending' to 'completed'
```

**Diagnosis**:
The system detected an illegal state transition.

**Solution**:
Follow the correct lifecycle:
```
pending → in_progress → testing → completed
```

**Example Fix**:
```bash
# Current: F001 status is 'pending'
# ❌ Wrong: Try to mark as 'completed'

# ✅ Correct workflow:
# 1. Start development
python3 scripts/adds.py start
# → Status: pending → in_progress

# 2. Finish implementation
# → Status: in_progress → testing

# 3. Run tests
python3 scripts/adds.py start
# → Status: testing → completed
```

### Problem: "Compliance score too low"

**Symptom**:
```bash
python3 scripts/adds.py status
# Compliance Score: 0.45 (needs attention)
```

**Diagnosis**:
```bash
# Check violations
cat .ai/progress.md | grep "VIOLATION"

# Example output:
# VIOLATION: Multiple features in session (F003, F004)
# VIOLATION: Invalid transition (pending → completed)
# VIOLATION: Missing evidence for F005
```

**Solutions**:

**Violation 1: Multiple features in session**
```bash
# Start new session and focus on one feature
python3 scripts/adds.py start
# Latch will prevent switching
```

**Violation 2: Invalid transition**
```bash
# Fix the transition in feature_list.md
vim .ai/feature_list.md
# Change status back to valid state
```

**Violation 3: Missing evidence**
```bash
# Add evidence for completed features
python3 scripts/adds.py start
# Tester Agent will verify and add evidence
```

### Problem: "Latch prevents feature switch"

**Symptom**:
```
Error: Feature latch is locked to F003
```

**Diagnosis**:
This is expected behavior (preventing state thrashing).

**Solution**:
```bash
# Option 1: Continue with F003 (recommended)
python3 scripts/adds.py start

# Option 2: Manually release latch (not recommended)
python3 scripts/adds.py stop --release-latch
```

### Problem: "Agent boundary violation"

**Symptom**:
```
Error: PM Agent cannot perform 'implement_feature'
```

**Diagnosis**:
Each agent has specific permissions.

**Solution**:
Use the correct agent:
```bash
# Check recommended agent
python3 scripts/adds.py route

# Output:
# 📍 Recommended Agent: Developer Agent
#    Reason: Pending features need implementation
```

---

## Advanced Patterns

### Pattern 1: Parallel Development (Multiple Branches)

```bash
# Create feature branch
git checkout -b feature/F001-user-auth

# Initialize branch-specific progress
python3 scripts/adds.py branch init F001

# Work on F001 in isolation
python3 scripts/adds.py start

# Meanwhile, another developer works on F002
git checkout -b feature/F002-task-crud
python3 scripts/adds.py branch init F002
```

### Pattern 2: Regression Testing

```bash
# Before adding new features
python3 scripts/adds.py start --regression-check

# Tester Agent will:
# 1. Run all tests for completed features
# 2. Verify no regressions
# 3. Report status
```

### Pattern 3: Incremental Rollout

```bash
# Implement feature in stages
## F001-1: User Registration (Core)
- **Dependencies**: -
- **Status**: pending

## F001-2: User Registration (Email Verification)
- **Dependencies**: F001-1
- **Status**: pending

## F001-3: User Registration (Password Reset)
- **Dependencies**: F001-1, F001-2
- **Status**: pending
```

---

## Summary

### Key Takeaways

1. ✅ **Always check route** before starting
2. ✅ **Monitor compliance score** after each session
3. ✅ **Use latches** to prevent state thrashing
4. ✅ **Write detailed feature descriptions**
5. ✅ **Follow the feature lifecycle**
6. ✅ **Provide evidence** for status updates

### Quick Reference

```bash
# Daily workflow
python3 scripts/adds.py route    # Check agent
python3 scripts/adds.py start    # Start session
python3 scripts/adds.py status   # Check progress

# Troubleshooting
python3 scripts/adds.py validate # Validate state
python3 scripts/adds.py dag      # View dependencies

# Testing
python3 scripts/test_integration.py # Run all tests
```

---

**Need help?** Check [Troubleshooting](#troubleshooting) or review the [Quick Start Guide](quick-start.md) for more details.
