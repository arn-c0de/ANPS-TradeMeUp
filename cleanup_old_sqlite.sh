#!/bin/bash
echo "========================================"
echo "Cleanup: Remove old SQLite files"
echo "========================================"
echo ""
echo "This will delete:"
echo "  - Temporary migration scripts"
echo "  - Test files"
echo ""
echo "BACKUP will be kept:"
echo "  - trademeup.db (renamed to trademeup.db.backup)"
echo ""
read -p "Continue with cleanup? (y/n): " choice

if [ "$choice" != "y" ] && [ "$choice" != "Y" ]; then
    echo ""
    echo "[CANCELLED] No files were deleted"
    read -p "Press enter to continue..."
    exit 0
fi

echo ""
echo "[1] Moving SQLite database to backup..."
if [ -f "trademeup.db" ]; then
    mv trademeup.db trademeup.db.backup
    echo "[OK] trademeup.db renamed to trademeup.db.backup"
else
    echo "[INFO] trademeup.db not found"
fi

echo ""
echo "[2] Removing temporary migration scripts..."
if [ -f "scripts/migrate_sqlite_to_postgresql.py" ]; then
    rm scripts/migrate_sqlite_to_postgresql.py
    echo "[OK] Deleted migrate_sqlite_to_postgresql.py"
fi
if [ -f "scripts/migrate_remaining_data.py" ]; then
    rm scripts/migrate_remaining_data.py
    echo "[OK] Deleted migrate_remaining_data.py"
fi

echo ""
echo "[3] Removing test scripts..."
if [ -f "test_app_postgresql.bat" ]; then
    rm test_app_postgresql.bat
    echo "[OK] Deleted test_app_postgresql.bat"
fi

echo ""
echo "========================================"
echo "[SUCCESS] Cleanup complete!"
echo "========================================"
echo ""
echo "Your backup is at: trademeup.db.backup"
echo "You can delete it after 1-2 weeks of testing"
echo ""
read -p "Press enter to continue..."
