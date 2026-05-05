#!/usr/bin/env bash
# Helper script to ensure all requirements are installed

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

echo "[*] Checking and installing requirements..."

if [[ ! -f venv/bin/python ]]; then
    echo "[ERROR] Virtual environment not found"
    echo "[INFO] Run: bash setup.sh"
    exit 1
fi

# Activate venv
source venv/bin/activate

echo "[*] Upgrading pip..."
pip install --upgrade pip --break-system-packages --quiet 2>&1 | grep -v "externally-managed" || true

echo "[*] Installing requirements..."
pip install -r requirements.txt --break-system-packages --quiet 2>&1 | grep -v "externally-managed" || true

echo "[*] Verifying critical packages..."
python3 << 'EOF'
import sys
critical = ["mcp", "rich", "textual", "anthropic", "aiohttp"]
optional = ["evtx", "pytsk3", "volatility3"]

print("\n[CRITICAL PACKAGES]")
for pkg in critical:
    try:
        __import__(pkg)
        print(f"  ✓ {pkg}")
    except ImportError:
        print(f"  ✗ {pkg} - MISSING")
        sys.exit(1)

print("\n[OPTIONAL PACKAGES]")
for pkg in optional:
    try:
        __import__(pkg)
        print(f"  ✓ {pkg}")
    except ImportError:
        print(f"  ✗ {pkg} - install with: pip install python-evtx pytsk3 volatility3")

print("\n✅ All critical packages installed!")
EOF
