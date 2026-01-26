@echo off
REM Wrapper for RSS Fetch - Keeps terminal open on errors
REM Called by GUI to start RSS feed fetching in separate console

REM Change to project root directory
cd /d "%~dp0\.."

echo ================================================================================
echo TradeMeUp - RSS Feed Fetcher
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
echo Script: %CD%\scripts\run_rss_fetch.py
echo Working Dir: %CD%
echo Arguments: %*
echo.
echo Starting RSS feed fetcher...
echo ================================================================================
echo.

REM Run the RSS fetcher with venv Python
"%CD%\venv\Scripts\python.exe" "%CD%\scripts\run_rss_fetch.py" %*

REM Capture exit code
set EXIT_CODE=%ERRORLEVEL%

echo.
echo ================================================================================
if %EXIT_CODE% EQU 0 (
    echo RSS fetcher stopped normally (code: %EXIT_CODE%)
) else if %EXIT_CODE% EQU 130 (
    echo RSS fetcher stopped by user (Ctrl+C)
) else (
    echo ERROR: RSS fetcher failed with exit code %EXIT_CODE%
)
echo ================================================================================
echo.
echo Press any key to close this window...
pause >nul
