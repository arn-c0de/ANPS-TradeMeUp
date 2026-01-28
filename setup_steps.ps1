# TradeMeUp PostgreSQL Setup - PowerShell Version
# Führen Sie diese Datei aus mit: .\setup_steps.ps1

Write-Host "============================================================" -ForegroundColor Cyan
Write-Host "TradeMeUp - PostgreSQL Setup" -ForegroundColor Cyan
Write-Host "============================================================" -ForegroundColor Cyan
Write-Host ""

# Check if venv exists
if (-not (Test-Path "venv")) {
    Write-Host "[ERROR] Virtual environment not found!" -ForegroundColor Red
    Write-Host "Please create it first: python -m venv venv" -ForegroundColor Yellow
    exit 1
}

Write-Host "[1/5] Activating virtual environment..." -ForegroundColor Green
& ".\venv\Scripts\Activate.ps1"

Write-Host "[2/5] Installing pgvector..." -ForegroundColor Green
& ".\venv\Scripts\pip.exe" install pgvector

Write-Host "[3/5] Testing PostgreSQL connection..." -ForegroundColor Green
& ".\venv\Scripts\python.exe" test_postgresql_connection.py

if ($LASTEXITCODE -ne 0) {
    Write-Host ""
    Write-Host "[ERROR] PostgreSQL connection failed!" -ForegroundColor Red
    Write-Host ""
    Write-Host "Please check:" -ForegroundColor Yellow
    Write-Host "  1. Is PostgreSQL running?" -ForegroundColor Yellow
    Write-Host "  2. Is DATABASE_URL correct in .env.local?" -ForegroundColor Yellow
    Write-Host "  3. Does database 'trademeup' exist?" -ForegroundColor Yellow
    Write-Host ""
    Write-Host "See POSTGRESQL_SETUP.md for detailed instructions" -ForegroundColor Cyan
    Read-Host "Press Enter to continue"
    exit 1
}

Write-Host ""
Write-Host "[4/5] Running Alembic migrations..." -ForegroundColor Green
& ".\venv\Scripts\alembic.exe" upgrade head

if ($LASTEXITCODE -ne 0) {
    Write-Host ""
    Write-Host "[ERROR] Migrations failed!" -ForegroundColor Red
    Write-Host "Check the error message above" -ForegroundColor Yellow
    Read-Host "Press Enter to continue"
    exit 1
}

Write-Host ""
Write-Host "[5/5] Verifying database tables..." -ForegroundColor Green
& ".\venv\Scripts\python.exe" tests\checks\check_tables.py

Write-Host ""
Write-Host "============================================================" -ForegroundColor Green
Write-Host "[SUCCESS] PostgreSQL Setup Complete!" -ForegroundColor Green
Write-Host "============================================================" -ForegroundColor Green
Write-Host ""
Write-Host "You can now:" -ForegroundColor Cyan
Write-Host "  1. Start GUI: .\start_gui.bat" -ForegroundColor White
Write-Host "  2. Run pipeline: python scripts\run_continuous_pipeline.py" -ForegroundColor White
Write-Host "  3. Benchmark: python scripts\benchmark_postgresql.py" -ForegroundColor White
Write-Host ""
Read-Host "Press Enter to close"
