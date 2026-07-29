#!/bin/bash
# Wrapper for Backfill Script - Keeps terminal open on errors
# Called by GUI to start backfill in separate console

# Change to project root directory
cd "$(dirname "$0")/.."

echo "================================================================================"
echo "TradeMeUp - Backfill All Agents"
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

SCRIPT_PATH="$(pwd)/scripts/backfill_all_agents.py"
WORK_DIR="$(pwd)"

echo "Python: $PYTHON_BIN"
echo "Script: $SCRIPT_PATH"
echo "Working Dir: $WORK_DIR"
echo "Arguments: $*"
echo ""
echo "Starting backfill..."
echo "================================================================================"
echo ""

# Run the backfill
"$PYTHON_BIN" "$SCRIPT_PATH" "$@"

# Capture exit code
EXIT_CODE=$?

echo ""
echo "================================================================================"
if [ $EXIT_CODE -eq 0 ]; then
    echo "Backfill completed successfully (code: $EXIT_CODE)"
else
    echo "ERROR: Backfill failed with exit code $EXIT_CODE"
fi
echo "================================================================================"
echo ""
pause_if_interactive "Press enter to close this window..."
