@echo off
echo ============================================================
echo TradeMeUp - PostgreSQL  Setup
echo ============================================================
echo.

for %%I in ("%~dp0..\..") do set "ROOT_DIR=%%~fI"
cd /d "%ROOT_DIR%"

REM Check if venv exists
if not exist "venv\" (
    echo [ERROR] Virtual environment not found!
    echo Please create it first: python -m venv venv
    exit /b 1
)

echo [1/5] Activating virtual environment...
call venv\Scripts\activate.bat

echo [2/5] Installing pgvector...
pip install pgvector

echo [3/5] Testing PostgreSQL connection...
python scripts\db\test_db_connection.py

if %ERRORLEVEL% NEQ 0 (
    echo.
    echo [ERROR] PostgreSQL connection failed!
    echo.
    echo Please check:
    echo   1. Is PostgreSQL running?
    echo   2. Is DATABASE_URL correct in .env.local?
    echo   3. Does database 'trademeup' exist?
    echo.
    echo See docs\setup\POSTGRESQL_SETUP.md for detailed instructions
    pause
    exit /b 1
)

echo.
echo [4/5] Running Alembic migrations...
alembic upgrade head

if %ERRORLEVEL% NEQ 0 (
    echo.
    echo [ERROR] Migrations failed!
    echo Check the error message above
    pause
    exit /b 1
)

echo.
echo [5/5] Verifying database tables...
python tests\checks\check_tables.py

echo.
echo ============================================================
echo [SUCCESS] PostgreSQL Setup Complete!
echo ============================================================
echo.
echo You can now:
echo   1. Start GUI: scripts\runtime\start_gui.bat
echo   2. Run pipeline: python scripts\run_continuous_pipeline.py
echo   3. Benchmark: python scripts\benchmark_postgresql.py
echo.
pause
