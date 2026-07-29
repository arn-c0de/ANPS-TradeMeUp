#!/bin/bash
# Wrapper for MVP Pipeline - Keeps terminal open on errors
# Called by GUI to start MVP pipeline in separate console

# Change to project root directory
cd "$(dirname "$0")/.."

echo "================================================================================"
echo "TradeMeUp - MVP Pipeline"
echo "================================================================================"
echo ""

# Resolve the interpreter: ./venv on a developer machine, the system Python
# inside the container, where dependencies are installed globally.
# shellcheck source=scripts/lib/python_env.sh
. "$(pwd)/scripts/lib/python_env.sh"
if ! resolve_python; then
    pause_if_interactive "Press enter to continue..."
    exit 1
fi

SCRIPT_PATH="$(pwd)/scripts/run_mvp_pipeline.py"
WORK_DIR="$(pwd)"

echo "Python: $PYTHON_BIN"
echo "Script: $SCRIPT_PATH"
echo "Working Dir: $WORK_DIR"
echo "Arguments: $*"
echo ""
echo "Starting MVP pipeline..."
echo "================================================================================"
echo ""

# Run the pipeline
"$PYTHON_BIN" "$SCRIPT_PATH" "$@"

# Capture exit code
EXIT_CODE=$?

echo ""
echo "================================================================================"
if [ $EXIT_CODE -eq 0 ]; then
    echo "Pipeline completed successfully (code: $EXIT_CODE)"
else
    echo "ERROR: Pipeline failed with exit code $EXIT_CODE"
fi
echo "================================================================================"
echo ""
pause_if_interactive "Press enter to close this window..."
