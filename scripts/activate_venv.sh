#!/bin/bash
# Activate virtual environment for Blueplane Telemetry Core

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"
VENV_DIR="$PROJECT_DIR/.venv"

if [ ! -d "$VENV_DIR" ]; then
    echo "Virtual environment not found. Run scripts/setup_venv.sh first."
    exit 1
fi

source "$VENV_DIR/bin/activate"
echo "✅ Virtual environment activated"

