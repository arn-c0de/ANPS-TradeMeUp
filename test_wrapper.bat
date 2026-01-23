@echo off
REM Simple test to verify wrapper script works

echo Testing wrapper script...
echo.

REM Test 1: Check if wrapper exists
if not exist "scripts\run_continuous_pipeline_wrapper.bat" (
    echo FAIL: Wrapper script not found
    pause
    exit /b 1
)
echo PASS: Wrapper script exists

REM Test 2: Check if venv exists
if not exist "venv\Scripts\python.exe" (
    echo FAIL: venv not found
    pause
    exit /b 1
)
echo PASS: venv exists

REM Test 3: Try to start the wrapper (will open new window)
echo.
echo Opening pipeline in new window...
echo (Check the new window that opens)
echo.

start "TradeMeUp Pipeline Test" scripts\run_continuous_pipeline_wrapper.bat --interval 300

echo.
echo New window should have opened.
echo Check it for any errors!
echo.
pause
