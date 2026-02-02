#!/bin/bash
# ============================================================================
# TradeMeUp - One-Click Setup and Start
# ============================================================================
# This script does everything:
# 1. Creates venv
# 2. Installs dependencies
# 3. Checks Ollama
# 4. Starts both pipeline AND dashboard
# ============================================================================

echo "================================================================================"
echo "🚀 TradeMeUp - Complete Setup and Launch"
echo "================================================================================"
echo ""

# Change to project directory
cd "$(dirname "$0")"

# Check Python installation
echo "🔍 Checking Python installation..."
if ! command -v python3 &> /dev/null; then
    echo "❌ Python not found! Please install Python 3.12+"
    read -p "Press enter to continue..."
    exit 1
fi
echo "✅ Python found"
echo ""

# Create venv if needed
if [ ! -d "venv" ]; then
    echo "📦 Creating virtual environment..."
    python3 -m venv venv
    if [ $? -ne 0 ]; then
        echo "❌ Error creating virtual environment"
        read -p "Press enter to continue..."
        exit 1
    fi
    echo "✅ Virtual environment created"
else
    echo "✅ Virtual environment exists"
fi
echo ""

# Activate venv
echo "🔧 Activating virtual environment..."
source venv/bin/activate
if [ $? -ne 0 ]; then
    echo "❌ Error activating virtual environment"
    read -p "Press enter to continue..."
    exit 1
fi
echo "✅ Activated"
echo ""

# Install dependencies
echo "📚 Installing/updating dependencies..."
python -m pip install --upgrade pip --quiet
pip install -r requirements.txt --quiet
if [ $? -ne 0 ]; then
    echo "⚠️ Some dependencies may have issues"
fi
echo "✅ Dependencies ready"
echo ""

# Check Ollama
echo "🤖 Checking Ollama LLM service..."
if ! curl -s http://localhost:11434/api/tags > /dev/null 2>&1; then
    echo "⚠️ Ollama not running!"
    echo "💡 Start Ollama manually or install from: https://ollama.ai"
    echo ""
    read -p "Continue without Ollama? (y/n): " continue
    if [ "$continue" != "y" ] && [ "$continue" != "Y" ]; then
        exit 1
    fi
else
    echo "✅ Ollama is running"
fi
echo ""

# Create necessary directories
mkdir -p models logs
echo "✅ Directories ready"
echo ""

# Ask what to start
echo "================================================================================"
echo "What would you like to start?"
echo "================================================================================"
echo ""
echo "[1] GUI Dashboard only"
echo "[2] Agent Pipeline only"
echo "[3] Both (Pipeline in background + Dashboard)"
echo ""
read -p "Enter choice (1-3): " start_choice
echo ""

case $start_choice in
    1)
        echo "🌐 Starting Dashboard..."
        echo "💡 Visit: http://localhost:8050"
        echo ""
        python run_dashboard.py
        ;;
    2)
        echo "🤖 Starting Pipeline..."
        echo ""
        python scripts/run_mvp_pipeline.py
        read -p "Press enter to continue..."
        ;;
    3)
        echo "🚀 Starting Pipeline in background..."
        python scripts/run_mvp_pipeline.py &
        sleep 3
        echo ""
        echo "🌐 Starting Dashboard..."
        echo "💡 Visit: http://localhost:8050"
        echo ""
        python run_dashboard.py
        ;;
    *)
        echo "❌ Invalid choice"
        read -p "Press enter to continue..."
        exit 1
        ;;
esac

if [ $? -ne 0 ]; then
    echo ""
    echo "❌ Error occurred"
    read -p "Press enter to continue..."
fi
