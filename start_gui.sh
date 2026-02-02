#!/bin/bash
# ============================================================================
# TradeMeUp - GUI Dashboard Starter
# ============================================================================
# This script:
# 1. Creates virtual environment if needed
# 2. Installs/updates requirements
# 3. Starts the Dash dashboard
# ============================================================================

echo "================================================================================"
echo "🚀 TradeMeUp - Starting GUI Dashboard"
echo "================================================================================"
echo ""

# Change to project directory
cd "$(dirname "$0")"

# Check if venv exists
if [ ! -d "venv" ]; then
    echo "📦 Creating virtual environment..."
    python3 -m venv venv
    if [ $? -ne 0 ]; then
        echo "❌ Error creating virtual environment"
        read -p "Press enter to continue..."
        exit 1
    fi
    echo "✅ Virtual environment created"
    echo ""
fi

# Activate virtual environment
echo "🔧 Activating virtual environment..."
source venv/bin/activate
if [ $? -ne 0 ]; then
    echo "❌ Error activating virtual environment"
    read -p "Press enter to continue..."
    exit 1
fi
echo "✅ Virtual environment activated"
echo ""

# Install/update requirements
echo "📚 Installing dependencies from requirements.txt..."
python -m pip install --upgrade pip --quiet
pip install -r requirements.txt --quiet
if [ $? -ne 0 ]; then
    echo "⚠️ Warning: Some dependencies may not have installed correctly"
    echo ""
fi
echo "✅ Dependencies installed"
echo ""

# Start dashboard
echo "================================================================================"
echo "🌐 Starting Dashboard..."
echo "================================================================================"
echo ""
python run_dashboard.py

# If dashboard exits with errors
if [ $? -ne 0 ]; then
    echo ""
    echo "❌ Dashboard exited with errors"
    read -p "Press enter to continue..."
fi
