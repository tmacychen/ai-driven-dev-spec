#!/bin/bash
# init.sh - Automated Environment Setup for AI Agents
# This script must be idempotent: safe to run multiple times.
set -e

echo "=== AI-Driven Dev: Environment Bootstrap ==="

# --- Step 1: Install Dependencies ---
echo "[1/4] Checking and installing dependencies..."

# Node.js projects
if [ -f "package.json" ]; then
    if [ ! -d "node_modules" ]; then
        echo "  → Installing npm dependencies..."
        npm install
    else
        echo "  ✓ npm dependencies already installed."
    fi
fi

# Python projects
if [ -f "requirements.txt" ]; then
    if [ ! -d "venv" ]; then
        echo "  → Creating Python virtual environment..."
        python3 -m venv venv
    fi
    echo "  → Installing Python dependencies..."
    source venv/bin/activate
    pip install -r requirements.txt -q
fi

# --- Step 2: Validate Project State ---
echo "[2/4] Validating project state..."

# Check .ai directory exists
if [ ! -d ".ai" ]; then
    echo "  ⚠ .ai/ directory not found. Please run Initializer Agent first."
    exit 1
fi

if [ ! -f ".ai/feature_list.json" ]; then
    echo "  ⚠ .ai/feature_list.json not found."
    exit 1
fi

echo "  ✓ Project state files found."

# --- Step 3: Start Development Services (if applicable) ---
echo "[3/4] Starting backend services..."

# Detect and start services based on project type
# Uncomment and customize as needed:
#
# if [ -f "package.json" ]; then
#     # Check if dev server is already running
#     if ! curl -s http://localhost:3000/health > /dev/null 2>&1; then
#         echo "  → Starting dev server..."
#         npm run dev &
#         sleep 3
#     else
#         echo "  ✓ Dev server already running."
#     fi
# fi

echo "  ✓ Service check complete."

# --- Step 4: Run Smoke Tests ---
echo "[4/4] Running basic health checks..."

# Quick sanity check
if [ -f "package.json" ] && grep -q '"test"' package.json; then
    echo "  → Running smoke tests..."
    npm test -- --watchAll=false 2>/dev/null || echo "  ⚠ Some tests failed. Check output above."
elif [ -f "pytest.ini" ] || [ -f "setup.py" ] || [ -f "pyproject.toml" ]; then
    echo "  → Running smoke tests..."
    pytest tests/ -x -q 2>/dev/null || echo "  ⚠ Some tests failed. Check output above."
else
    echo "  ℹ No test runner detected. Skipping smoke tests."
fi

echo ""
echo "=== Setup Complete ==="
echo "Project is ready for development."
echo "Run 'cat progress.log' to see current status."
