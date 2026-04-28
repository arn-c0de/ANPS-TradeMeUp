@echo off
REM ============================================================================
REM TradeMeUp - Agent Pipeline Starter
REM ============================================================================
REM This script runs the full AI agent pipeline:
REM - Fetches news from RSS feeds
REM - Processes and analyzes content
REM - Generates predictions
REM ============================================================================

echo ================================================================================
echo 🤖 TradeMeUp - Starting Agent Pipeline
echo ================================================================================
echo.

REM Change to project root
for %%I in ("%~dp0..\..") do set "ROOT_DIR=%%~fI"
cd /d "%ROOT_DIR%"

REM Check if venv exists
if not exist "venv\" (
    echo ❌ Virtual environment not found!
    echo 💡 Please run scripts\runtime\start_gui.bat first to set up the environment
    pause
    exit /b 1
)

REM Activate virtual environment
echo 🔧 Activating virtual environment...
call venv\Scripts\activate.bat
if errorlevel 1 (
    echo ❌ Error activating virtual environment
    pause
    exit /b 1
)
echo ✅ Virtual environment activated
echo.

REM Show menu
echo ================================================================================
echo Select Pipeline Mode:
echo ================================================================================
echo.
echo [1] Full Pipeline (All Agents - ~15 minutes)
echo [2] Quick Test (5 articles - ~2 minutes)
echo [3] Single Agent Test
echo [4] Continuous Mode (runs indefinitely)
echo.
set /p choice="Enter choice (1-4): "

echo.
echo ================================================================================

if "%choice%"=="1" (
    echo 🚀 Running FULL PIPELINE...
    echo.
    python scripts\run_full_pipeline.py
) else if "%choice%"=="2" (
    echo ⚡ Running QUICK TEST...
    echo.
    python scripts\run_mvp_pipeline.py
) else if "%choice%"=="3" (
    echo.
    echo Available Agents:
    echo [1] Data Ingestion Agent
    echo [2] Data Quality Agent
    echo [3] Content Understanding Agent
    echo [4] Entity Mapping Agent
    echo [5] Impact Scoring Agent
    echo [6] Surprise Quantification Agent
    echo [7] Regime Detection Agent
    echo [8] Prediction Agent
    echo.
    set /p agent_choice="Enter agent number (1-8): "
    echo.
    python scripts\run_ingestion.py --agent !agent_choice!
) else if "%choice%"=="4" (
    echo 🔄 Running CONTINUOUS MODE...
    echo 💡 Press CTRL+C to stop
    echo.
    :continuous_loop
    python scripts\run_full_pipeline.py
    echo.
    echo ⏳ Waiting 30 minutes before next run...
    timeout /t 1800 /nobreak
    goto continuous_loop
) else (
    echo ❌ Invalid choice
    pause
    exit /b 1
)

echo.
echo ================================================================================
echo ✅ Pipeline completed
echo ================================================================================
pause
