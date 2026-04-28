@echo off
REM ============================================================================
REM TradeMeUp - One-Click Setup and Start
REM ============================================================================
REM This script does everything:
REM 1. Creates venv
REM 2. Installs dependencies
REM 3. Checks Ollama
REM 4. Starts both pipeline AND dashboard
REM ============================================================================

echo ================================================================================
echo 🚀 TradeMeUp - Complete Setup and Launch
echo ================================================================================
echo.

REM Change to project root
for %%I in ("%~dp0..\..") do set "ROOT_DIR=%%~fI"
cd /d "%ROOT_DIR%"

REM Check Python installation
echo 🔍 Checking Python installation...
python --version >nul 2>&1
if errorlevel 1 (
    echo ❌ Python not found! Please install Python 3.12+
    pause
    exit /b 1
)
echo ✅ Python found
echo.

REM Create venv if needed
if not exist "venv\" (
    echo 📦 Creating virtual environment...
    python -m venv venv
    if errorlevel 1 (
        echo ❌ Error creating virtual environment
        pause
        exit /b 1
    )
    echo ✅ Virtual environment created
) else (
    echo ✅ Virtual environment exists
)
echo.

REM Activate venv
echo 🔧 Activating virtual environment...
call venv\Scripts\activate.bat
if errorlevel 1 (
    echo ❌ Error activating virtual environment
    pause
    exit /b 1
)
echo ✅ Activated
echo.

REM Install dependencies
echo 📚 Installing/updating dependencies...
python -m pip install --upgrade pip --quiet
pip install -r requirements.txt --quiet
if errorlevel 1 (
    echo ⚠️ Some dependencies may have issues
)
echo ✅ Dependencies ready
echo.

REM Check Ollama
echo 🤖 Checking Ollama LLM service...
curl -s http://localhost:11434/api/tags >nul 2>&1
if errorlevel 1 (
    echo ⚠️ Ollama not running!
    echo 💡 Start Ollama manually or install from: https://ollama.ai
    echo.
    set /p continue="Continue without Ollama? (y/n): "
    if /i not "!continue!"=="y" exit /b 1
) else (
    echo ✅ Ollama is running
)
echo.

REM Create necessary directories
if not exist "models\" mkdir models
if not exist "logs\" mkdir logs
echo ✅ Directories ready
echo.

REM Ask what to start
echo ================================================================================
echo What would you like to start?
echo ================================================================================
echo.
echo [1] GUI Dashboard only
echo [2] Agent Pipeline only
echo [3] Both (Pipeline in background + Dashboard)
echo.
set /p start_choice="Enter choice (1-3): "
echo.

if "%start_choice%"=="1" (
    echo 🌐 Starting Dashboard...
    echo 💡 Visit: http://localhost:8050
    echo.
    python scripts\runtime\run_dashboard.py
) else if "%start_choice%"=="2" (
    echo 🤖 Starting Pipeline...
    echo.
    python scripts\run_mvp_pipeline.py
    pause
) else if "%start_choice%"=="3" (
    echo 🚀 Starting Pipeline in background...
    start /B python scripts\run_mvp_pipeline.py
    timeout /t 3 /nobreak >nul
    echo.
    echo 🌐 Starting Dashboard...
    echo 💡 Visit: http://localhost:8050
    echo.
    python scripts\runtime\run_dashboard.py
) else (
    echo ❌ Invalid choice
    pause
    exit /b 1
)

if errorlevel 1 (
    echo.
    echo ❌ Error occurred
    pause
)
