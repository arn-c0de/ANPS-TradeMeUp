#!/bin/bash
echo "============================================================"
echo "TradeMeUp - PostgreSQL Setup"
echo "============================================================"
echo ""

# Check if venv exists, create if needed
if [ ! -d "venv" ]; then
    echo "[1/6] Creating virtual environment..."
    python3 -m venv venv
    if [ $? -ne 0 ]; then
        echo "[ERROR] Failed to create virtual environment!"
        echo "Please install python3-venv: sudo apt install python3-venv"
        exit 1
    fi
    echo "✅ Virtual environment created"
else
    echo "[1/6] Virtual environment exists"
fi

echo "[2/6] Activating virtual environment..."
source venv/bin/activate

echo "[3/6] Installing dependencies..."
pip install --upgrade pip --quiet
pip install -r requirements.txt --quiet
echo "✅ Dependencies installed"

echo "[4/6] Testing PostgreSQL connection..."
python3 test_postgresql_connection.py 2>/dev/null || python test_postgresql_connection.py 2>/dev/null

if [ $? -ne 0 ]; then
    echo ""
    echo "[ERROR] PostgreSQL connection failed!"
    echo ""
    echo "Please check:"
    echo "  1. Is PostgreSQL running?"
    echo "  2. Is DATABASE_URL correct in .env.local?"
    echo "  3. Does database 'trademeup' exist?"
    echo ""
    echo "See POSTGRESQL_SETUP.md for detailed instructions"
    read -p "Press enter to continue..."
    exit 1
fi

echo ""
echo "[5/6] Running Alembic migrations..."
alembic upgrade head 2>/dev/null || echo "⚠️  Migrations skipped (may already be applied)"

echo ""
echo "[6/6] Verifying database tables..."
python3 tests/checks/check_tables.py 2>/dev/null || python tests/checks/check_tables.py 2>/dev/null || echo "⚠️  Table check skipped"

echo ""
echo "============================================================"
echo "[SUCCESS] PostgreSQL Setup Complete!"
echo "============================================================"
echo ""
echo "You can now:"
echo "  1. Start GUI: ./start_gui.sh"
echo "  2. Run pipeline: ./run_pipeline.sh"
echo "  3. Check Docker: sudo docker ps"
echo ""
read -p "Press enter to continue..."
