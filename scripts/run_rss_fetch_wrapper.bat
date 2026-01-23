@echo off
REM Wrapper for RSS Feed Fetcher - Keeps console open
REM This ensures the console window stays open even if the script fails

title TradeMeUp - RSS Feed Fetcher

echo.
echo ========================================
echo TradeMeUp - RSS Feed Fetcher
echo ========================================
echo.

REM Run the Python script
python "%~dp0run_rss_fetch.py"

REM Check exit code
if %ERRORLEVEL% EQU 0 (
    echo.
    echo [SUCCESS] RSS fetch completed
) else (
    echo.
    echo [ERROR] RSS fetch failed with code %ERRORLEVEL%
)

echo.
echo Press any key to close this window...
pause >nul
