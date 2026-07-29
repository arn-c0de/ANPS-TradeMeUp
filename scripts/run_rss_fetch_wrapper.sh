#!/bin/bash
# Wrapper for RSS Fetch - Keeps terminal open on errors
# Called by GUI to start RSS feed fetching in separate console

# Change to project root directory
cd "$(dirname "$0")/.."

echo "================================================================================"
echo "TradeMeUp - RSS Feed Fetcher"
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

SCRIPT_PATH="$(pwd)/scripts/run_rss_fetch.py"
WORK_DIR="$(pwd)"

echo "Python: $PYTHON_BIN"
echo "Script: $SCRIPT_PATH"
echo "Working Dir: $WORK_DIR"
echo "Arguments: $*"
echo ""
echo "Starting RSS feed fetcher..."
echo "================================================================================"
echo ""

# Run the RSS fetcher
"$PYTHON_BIN" "$SCRIPT_PATH" "$@"

# Capture exit code
EXIT_CODE=$?

echo ""
echo "================================================================================"
if [ $EXIT_CODE -eq 0 ]; then
    echo "RSS fetcher stopped normally (code: $EXIT_CODE)"
elif [ $EXIT_CODE -eq 130 ]; then
    echo "RSS fetcher stopped by user (Ctrl+C)"
else
    echo "ERROR: RSS fetcher failed with exit code $EXIT_CODE"
fi
echo "================================================================================"
echo ""
pause_if_interactive "Press enter to close this window..."
