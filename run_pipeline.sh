#!/bin/bash
# ============================================================================
# TradeMeUp - Agent Pipeline Starter
# ============================================================================
# This script runs the full AI agent pipeline:
# - Fetches news from RSS feeds
# - Processes and analyzes content
# - Generates predictions
# ============================================================================

echo "================================================================================"
echo "🤖 TradeMeUp - Starting Agent Pipeline"
echo "================================================================================"
echo ""

# Change to project directory
cd "$(dirname "$0")"

# Check if venv exists
if [ ! -d "venv" ]; then
    echo "❌ Virtual environment not found!"
    echo "💡 Please run start_gui.sh first to set up the environment"
    read -p "Press enter to continue..."
    exit 1
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

# Show menu
echo "================================================================================"
echo "Select Pipeline Mode:"
echo "================================================================================"
echo ""
echo "[1] Full Pipeline (All Agents - ~15 minutes)"
echo "[2] Quick Test (5 articles - ~2 minutes)"
echo "[3] Single Agent Test"
echo "[4] Continuous Mode (runs indefinitely)"
echo ""
read -p "Enter choice (1-4): " choice

echo ""
echo "================================================================================"

case $choice in
    1)
        echo "🚀 Running FULL PIPELINE..."
        echo ""
        python scripts/run_full_pipeline.py
        ;;
    2)
        echo "⚡ Running QUICK TEST..."
        echo ""
        python scripts/run_mvp_pipeline.py
        ;;
    3)
        echo ""
        echo "Available Agents:"
        echo "[1] Data Ingestion Agent"
        echo "[2] Data Quality Agent"
        echo "[3] Content Understanding Agent"
        echo "[4] Entity Mapping Agent"
        echo "[5] Impact Scoring Agent"
        echo "[6] Surprise Quantification Agent"
        echo "[7] Regime Detection Agent"
        echo "[8] Prediction Agent"
        echo ""
        read -p "Enter agent number (1-8): " agent_choice
        echo ""
        python scripts/run_ingestion.py --agent $agent_choice
        ;;
    4)
        echo "🔄 Running CONTINUOUS MODE..."
        echo "💡 Press CTRL+C to stop"
        echo ""
        while true; do
            python scripts/run_full_pipeline.py
            echo ""
            echo "⏳ Waiting 30 minutes before next run..."
            sleep 1800
        done
        ;;
    *)
        echo "❌ Invalid choice"
        read -p "Press enter to continue..."
        exit 1
        ;;
esac

echo ""
echo "================================================================================"
echo "✅ Pipeline completed"
echo "================================================================================"
read -p "Press enter to continue..."
