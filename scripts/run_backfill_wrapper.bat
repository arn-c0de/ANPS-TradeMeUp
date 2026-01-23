@echo off
REM Wrapper for Backfill Script - Keeps terminal open on errors
REM Called by GUI to start backfill in separate console

REM Change to project root directory
cd /d "%~dp0\.."

echo ================================================================================
echo TradeMeUp - Backfill All Agents
echo ================================================================================
echo.

REM Check if venv Python exists
if not exist "venv\Scripts\python.exe" (
    echo ERROR: Virtual environment not found!
    echo Expected: %CD%\venv\Scripts\python.exe
    echo.
    echo Please run: python -m venv venv
    echo Then install requirements: venv\Scripts\pip install -r requirements.txt
    echo.
    pause
    exit /b 1
)

echo Python: %CD%\venv\Scripts\python.exe
echo Script: %CD%\scripts\backfill_all_agents.py
echo Working Dir: %CD%
echo Arguments: %*
echo.
echo Starting backfill...
echo ================================================================================
echo.

REM Run the backfill with venv Python
"%CD%\venv\Scripts\python.exe" "%CD%\scripts\backfill_all_agents.py" %*

REM Capture exit code
set EXIT_CODE=%ERRORLEVEL%

echo.
echo ================================================================================
if %EXIT_CODE% EQU 0 (
    echo Backfill completed successfully (code: %EXIT_CODE%)
) else (
    echo ERROR: Backfill failed with exit code %EXIT_CODE%
)
echo ================================================================================
echo.
echo Press any key to close this window...
pause >nul
