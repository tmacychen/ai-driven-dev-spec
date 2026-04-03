# Security Guidelines

> Command whitelist and security constraints

---

## Allowed Commands

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

---

## Forbidden Commands

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

## Command Guidelines

### ✅ DO

- Use package managers for dependencies
- Run tests in isolated environments
- Review scripts before execution
- Use read-only commands for inspection

### ❌ DON'T

- Execute commands with `sudo`
- Run scripts downloaded from the internet
- Modify system configurations
- Kill system processes

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
