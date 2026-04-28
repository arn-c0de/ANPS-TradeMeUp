#!/bin/bash
# TradeMeUp Continuous Pipeline Launcher
# Ensures the pipeline runs with the correct Python environment

echo "Starting TradeMeUp Continuous Pipeline..."
echo ""

# Change to project root
ROOT_DIR="$(cd "$(dirname "$0")/../.." && pwd)"
cd "$ROOT_DIR"

# Check if venv exists
if [ ! -f "venv/bin/python" ]; then
    echo "ERROR: Virtual environment not found!"
    echo "Please create venv first: python3 -m venv venv"
    read -p "Press enter to continue..."
    exit 1
fi

# Get absolute path to venv python
VENV_PYTHON="$(pwd)/venv/bin/python"
echo "Using Python: $VENV_PYTHON"
echo ""

# Start pipeline
"$VENV_PYTHON" scripts/run_continuous_pipeline.py "$@"

# If pipeline exits with error
if [ $? -ne 0 ]; then
    echo ""
    echo "ERROR: Pipeline exited with error code $?"
    read -p "Press enter to continue..."
fi
