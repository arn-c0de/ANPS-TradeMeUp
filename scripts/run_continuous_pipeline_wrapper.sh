#!/bin/bash
# Wrapper for Continuous Pipeline - Keeps terminal open on errors
# Called by GUI to start pipeline in separate console

# Change to project root directory
cd "$(dirname "$0")/.."

echo "================================================================================"
echo "TradeMeUp - Continuous Pipeline"
echo "================================================================================"
echo ""

# Check if venv Python exists
if [ ! -f "venv/bin/python" ]; then
    echo "ERROR: Virtual environment not found!"
    echo "Expected: $(pwd)/venv/bin/python"
    echo ""
    echo "Please run: python3 -m venv venv"
    echo "Then install requirements: venv/bin/pip install -r requirements.txt"
    echo ""
    read -p "Press enter to continue..."
    exit 1
fi

VENV_PYTHON="$(pwd)/venv/bin/python"
SCRIPT_PATH="$(pwd)/scripts/run_continuous_pipeline.py"
WORK_DIR="$(pwd)"

echo "Python: $VENV_PYTHON"
echo "Script: $SCRIPT_PATH"
echo "Working Dir: $WORK_DIR"
echo "Arguments: $*"
echo ""
echo "Starting pipeline..."
echo "================================================================================"
echo ""

# Run the pipeline with venv Python
"$VENV_PYTHON" "$SCRIPT_PATH" "$@"

# Capture exit code
EXIT_CODE=$?

echo ""
echo "================================================================================"
if [ $EXIT_CODE -eq 0 ]; then
    echo "Pipeline exited normally (code: $EXIT_CODE)"
else
    echo "ERROR: Pipeline crashed with exit code $EXIT_CODE"
fi
echo "================================================================================"
echo ""
read -p "Press enter to close this window..."
