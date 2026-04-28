@echo off
REM ============================================================================
REM TradeMeUp - GUI Dashboard Starter
REM ============================================================================
REM This script:
REM 1. Creates virtual environment if needed
REM 2. Installs/updates requirements
REM 3. Starts the Dash dashboard
REM ============================================================================

echo ================================================================================
echo 🚀 TradeMeUp - Starting GUI Dashboard
echo ================================================================================
echo.

REM Change to project root
for %%I in ("%~dp0..\..") do set "ROOT_DIR=%%~fI"
cd /d "%ROOT_DIR%"

REM Check if venv exists
if not exist "venv\" (
    echo 📦 Creating virtual environment...
    python -m venv venv
    if errorlevel 1 (
        echo ❌ Error creating virtual environment
        pause
        exit /b 1
    )
    echo ✅ Virtual environment created
    echo.
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

REM Install/update requirements
echo 📚 Installing dependencies from requirements.txt...
python -m pip install --upgrade pip --quiet
pip install -r requirements.txt --quiet
if errorlevel 1 (
    echo ⚠️ Warning: Some dependencies may not have installed correctly
    echo.
)
echo ✅ Dependencies installed
echo.

REM Start dashboard
echo ================================================================================
echo 🌐 Starting Dashboard...
echo ================================================================================
echo.
python scripts\runtime\run_dashboard.py

REM If dashboard exits, pause to see any errors
if errorlevel 1 (
    echo.
    echo ❌ Dashboard exited with errors
    pause
)
