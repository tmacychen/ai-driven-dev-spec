# Security Guidelines

> Command whitelist, permission model, and security constraints

---

## Layer 1: Static Command Whitelist

These commands are safe for AI Agents to execute:

| Category | Commands |
|----------|----------|
| **File Operations** | `ls`, `cat`, `head`, `tail`, `wc`, `grep`, `find`, `cp`, `mv` |
| **Node.js** | `npm`, `node`, `npx`, `yarn` |
| **Python** | `pip`, `python`, `pytest`, `black`, `flake8`, `mypy` |
| **Go** | `go`, `gofmt` |
| **Rust** | `cargo`, `rustc`, `rustfmt` |
| **Git** | All subcommands |
| **Build** | `make`, `cmake`, `gcc`, `clang` |

### Forbidden Commands

These commands are **NEVER** allowed:

| Command | Reason |
|---------|--------|
| `sudo`, `su` | System permission risk |
| `chmod`, `chown` (unless explicitly necessary) | Permission changes |
| `rm -rf /`, `mkfs`, `fdisk` | Irrecoverable data destruction |
| `nc`, `netcat`, `telnet` | Network backdoor risk |
| `iptables`, `route` | Network configuration changes |
| `curl \| bash`, `wget \| sh` | Unreviewed script execution |
| `kill -9` (system processes) | System stability |

---

## Layer 2: Three-Tier Permission Model (P0-4)

Beyond the static whitelist, ADDS implements a dynamic permission system:

### Permission Levels

| Level | Behavior | Example |
|-------|----------|---------|
| **Allow** | Execute automatically | `bash(ls*)`, `read(*)`, `write(./*)` |
| **Ask** | User confirmation required | `bash(rm*)`, `bash(git push*)`, `bash(npm install*)` |
| **Deny** | Blocked entirely | `bash(sudo*)`, `write(/etc/*)` |

### Permission Priority

```
Session config > CLI flags > Project settings (.ai/settings.json) > User defaults
```

### Permission Modes

| Mode | Description | Use Case |
|------|-------------|----------|
| `default` | Sensitive operations require confirmation | Normal development |
| `plan` | Read-only mode (no writes) | Exploration/review |
| `auto` | AI classifier auto-decides | Advanced users |
| `bypass` | All operations auto-approved | Trusted environments (dangerous) |

### Dead Loop Protection

- Same tool denied 3 consecutive times → 30s cooldown
- Total denial limit: 20 → fallback to human intervention

### Configuration

```json
// .ai/settings.json
{
  "permissions": {
    "mode": "default",
    "rules": {
      "allow": ["bash(ls*)", "read(*)", "write(./*)"],
      "ask": ["bash(rm*)", "bash(git push*)"],
      "deny": ["bash(sudo*)", "write(/etc/*)"]
    }
  }
}
```

---

## Command Guidelines

### ✅ DO

- Use package managers for dependencies
- Run tests in isolated environments
- Review scripts before execution
- Use read-only commands for inspection
- Check permission level before executing

### ❌ DON'T

- Execute commands with `sudo`
- Run scripts downloaded from the internet
- Modify system configurations
- Kill system processes
- Use `bypass` mode without understanding risks

---

## Package Installation

Installing dependencies via package managers is allowed:

```bash
# Node.js
npm install
npm install --save-dev jest

# Python
pip install -r requirements.txt
pip install pytest

# Rust
cargo build
cargo add serde

# Go
go mod download
go get github.com/gin-gonic/gin
```

---

## File Operations

### Safe Operations

```bash
# Reading
ls -la
cat file.txt
head -20 file.txt
tail -50 file.txt
grep "pattern" file.txt
find . -name "*.js"

# Copying/Moving
cp file.txt backup.txt
mv old.txt new.txt
```

### Destructive Operations (Use with Caution)

```bash
# Deleting (allowed but be careful)
rm file.txt
rm -rf node_modules/  # Sometimes necessary

# Modifying (allowed)
echo "content" > file.txt
```

---

## Network Operations

### Allowed

```bash
# Git operations
git clone https://github.com/user/repo.git
git pull
git push

# Package managers (implicit network)
npm install
pip install
cargo build
```

### Forbidden

```bash
# Direct network tools
curl https://example.com/script.sh | bash  # ❌
nc -l 8080  # ❌
telnet example.com  # ❌
```

---

## Memory Security (P0-3)

### Immutability Principle

- `.mem` files are APPEND-ONLY — historical records cannot be modified
- `index.mem` is the only mutable index — references can be updated
- Override operations append correction records, never delete originals

### Conflict Detection

- System Prompt vs Fixed Memory → System Prompt wins (automatic)
- User latest vs Fixed Memory → Recency Bias (automatic)
- System Prompt vs User latest → Must confirm with user

### Detox Mechanism

- Failure-driven invalidation marks wrong memories
- Negative penalty reduces priority of rollback-causing memories
- Lightweight conflict scan on every new memory write

---

## Validation

Use the validation script to check feature_list.md:

```bash
python scripts/adds.py validate
```

---

## Reporting Security Issues

If you discover a security vulnerability:

1. Do not open a public issue
2. Document the finding in `.ai/progress.md`
3. Notify the project maintainer
4. Wait for confirmation before disclosing
