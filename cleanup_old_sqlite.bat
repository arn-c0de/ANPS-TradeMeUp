@echo off
echo ========================================
echo Cleanup: Remove old SQLite files
echo ========================================
echo.
echo This will delete:
echo   - Temporary migration scripts
echo   - Test files
echo.
echo BACKUP will be kept:
echo   - trademeup.db (renamed to trademeup.db.backup)
echo.
choice /C YN /M "Continue with cleanup"
if errorlevel 2 goto :cancel

echo.
echo [1] Moving SQLite database to backup...
if exist trademeup.db (
    move trademeup.db trademeup.db.backup
    echo [OK] trademeup.db renamed to trademeup.db.backup
) else (
    echo [INFO] trademeup.db not found
)

echo.
echo [2] Removing temporary migration scripts...
if exist scripts\migrate_sqlite_to_postgresql.py (
    del scripts\migrate_sqlite_to_postgresql.py
    echo [OK] Deleted migrate_sqlite_to_postgresql.py
)
if exist scripts\migrate_remaining_data.py (
    del scripts\migrate_remaining_data.py
    echo [OK] Deleted migrate_remaining_data.py
)

echo.
echo [3] Removing test scripts...
if exist test_app_postgresql.bat (
    del test_app_postgresql.bat
    echo [OK] Deleted test_app_postgresql.bat
)

echo.
echo ========================================
echo [SUCCESS] Cleanup complete!
echo ========================================
echo.
echo Your backup is at: trademeup.db.backup
echo You can delete it after 1-2 weeks of testing
echo.
pause
goto :end

:cancel
echo.
echo [CANCELLED] No files were deleted
pause

:end
