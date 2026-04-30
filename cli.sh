#!/usr/bin/env bash
# Find Evil! CLI Launcher
# Direct access to main.py CLI

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

if [[ -f venv/bin/python ]]; then
    source venv/bin/activate
    python main.py "$@"
else
    echo "Error: Virtual environment not found or broken."
    echo ""
    echo "To fix this, run:"
    echo "  sudo apt-get install -y python3-venv python3-dev"
    echo "  bash setup.sh"
    echo ""
    exit 1
fi
