#!/bin/bash
# Setup virtual environment for Blueplane Telemetry Core

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"
VENV_DIR="$PROJECT_DIR/.venv"

echo "Setting up Python virtual environment..."

# Check Python version
if ! command -v python3 &> /dev/null; then
    echo "Error: python3 not found. Please install Python 3.11 or later."
    exit 1
fi

PYTHON_VERSION=$(python3 --version | cut -d' ' -f2 | cut -d'.' -f1,2)
REQUIRED_VERSION="3.11"

if [ "$(printf '%s\n' "$REQUIRED_VERSION" "$PYTHON_VERSION" | sort -V | head -n1)" != "$REQUIRED_VERSION" ]; then
    echo "Error: Python 3.11+ required. Found: $PYTHON_VERSION"
    exit 1
fi

# Create venv if it doesn't exist
if [ ! -d "$VENV_DIR" ]; then
    echo "Creating virtual environment at $VENV_DIR..."
    python3 -m venv "$VENV_DIR"
else
    echo "Virtual environment already exists at $VENV_DIR"
fi

# Activate venv
echo "Activating virtual environment..."
source "$VENV_DIR/bin/activate"

# Upgrade pip
echo "Upgrading pip..."
pip install --upgrade pip

# Install project
echo "Installing Blueplane Telemetry Core..."
pip install -e "$PROJECT_DIR"

echo ""
echo "✅ Virtual environment setup complete!"
echo ""
echo "To activate the virtual environment, run:"
echo "  source $VENV_DIR/bin/activate"
echo ""
echo "Or use the activate script:"
echo "  source scripts/activate_venv.sh"
echo ""

