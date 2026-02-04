#!/bin/bash
# TradeMeUp Pipeline Launcher - Optimized for GPU Memory Management
# Sets up environment and runs continuous pipeline

cd "$(dirname "$0")"

echo "================================================================================"
echo "🚀 TradeMeUp - Optimized Pipeline Launcher"
echo "================================================================================"
echo ""

echo "📦 Checking Python environment..."
if [ ! -f "venv/bin/python" ]; then
    echo "❌ ERROR: Virtual environment not found!"
    echo "Create venv: python3 -m venv venv"
    echo "Install requirements: venv/bin/pip install -r requirements.txt"
    exit 1
fi

# Note: Do NOT source .env here - Pydantic reads .env.local automatically
# Sourcing would export complex variables as shell strings, breaking JSON parsing

# Configure CUDA/PyTorch for GPU memory management
export PYTORCH_CUDA_ALLOC_CONF=expandable_segments:True
export TORCH_CUDA_EMPTY_CACHE=1

# Show configuration
echo ""
echo "Configuration:"
echo "  - LLM Provider: ${LLM_PROVIDER:-openai}"
echo "  - PyTorch CUDA: ${PYTORCH_CUDA_ALLOC_CONF}"
echo "  - Database: ${DATABASE_URL:-postgresql://localhost:5432/trademeup}"
echo ""

# Get absolute paths
VENV_PYTHON="$(pwd)/venv/bin/python"
SCRIPT_PATH="$(pwd)/scripts/run_continuous_pipeline.py"

echo "Starting pipeline..."
echo "  Python: $VENV_PYTHON"
echo "  Script: $SCRIPT_PATH"
echo ""
echo "================================================================================"
echo ""

# Run pipeline with environment variables
"$VENV_PYTHON" "$SCRIPT_PATH" "$@"

EXIT_CODE=$?
if [ $EXIT_CODE -ne 0 ]; then
    echo ""
    echo "⚠️  Pipeline exited with code $EXIT_CODE"
    read -p "Press enter to continue..."
fi

exit $EXIT_CODE
