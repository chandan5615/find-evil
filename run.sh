#!/usr/bin/env bash
# Find Evil! Launcher Script
# Activates venv and launches the TUI

set -euo pipefail

# Get script directory
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

# Check if venv exists and is valid
if [[ -f venv/bin/python ]]; then
    source venv/bin/activate
    python ui/tui.py "$@"
else
    echo "Error: Virtual environment not found or broken."
    echo ""
    echo "To fix this, run:"
    echo "  sudo apt-get install -y python3-venv python3-dev"
    echo "  bash setup.sh"
    echo ""
    exit 1
fi
