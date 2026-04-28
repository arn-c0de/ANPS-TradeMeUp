@echo off
REM TradeMeUp Continuous Pipeline Launcher
REM Ensures the pipeline runs with the correct Python environment

echo Starting TradeMeUp Continuous Pipeline...
echo.

for %%I in ("%~dp0..\..") do set "ROOT_DIR=%%~fI"
cd /d "%ROOT_DIR%"

REM Check if venv exists
if not exist "venv\Scripts\python.exe" (
    echo ERROR: Virtual environment not found!
    echo Please create venv first: python -m venv venv
    pause
    exit /b 1
)

REM Activate venv and start pipeline
echo Using Python: %cd%\venv\Scripts\python.exe
echo.

"%cd%\venv\Scripts\python.exe" scripts/run_continuous_pipeline.py %*

REM If pipeline exits with error
if %ERRORLEVEL% NEQ 0 (
    echo.
    echo ERROR: Pipeline exited with error code %ERRORLEVEL%
    pause
)
