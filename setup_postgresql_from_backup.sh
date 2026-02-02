#!/bin/bash
# ============================================================================
# TradeMeUp - PostgreSQL Setup with Backup Import
# ============================================================================
# This script:
# 1. Checks PostgreSQL installation
# 2. Creates database and user
# 3. Imports backup from external drive
# 4. Sets up environment configuration
# ============================================================================

set -e  # Exit on error

BACKUP_FILE="/media/arn/4E786B03786AE8E3/trademeup_backup.dump"
DB_NAME="trademeup"
DB_USER="trademeup_user"
DB_PASS="trademeup_pass"
DB_HOST="localhost"
DB_PORT="5432"

echo "================================================================================"
echo "🚀 TradeMeUp - PostgreSQL Setup with Backup Import"
echo "================================================================================"
echo ""
echo "Backup file: $BACKUP_FILE"
echo "Target database: $DB_NAME"
echo ""

# Check if backup file exists
if [ ! -f "$BACKUP_FILE" ]; then
    echo "❌ ERROR: Backup file not found!"
    echo "   Expected: $BACKUP_FILE"
    echo ""
    read -p "Press enter to exit..."
    exit 1
fi

BACKUP_SIZE=$(du -h "$BACKUP_FILE" | cut -f1)
echo "✅ Backup file found (Size: $BACKUP_SIZE)"
echo ""

# Check PostgreSQL installation
echo "🔍 Checking PostgreSQL installation..."
if ! command -v psql &> /dev/null; then
    echo "❌ PostgreSQL client (psql) not found!"
    echo ""
    echo "Install PostgreSQL:"
    echo "  Ubuntu/Debian: sudo apt install postgresql postgresql-contrib"
    echo "  Fedora/RHEL:   sudo dnf install postgresql postgresql-server"
    echo "  Arch:          sudo pacman -S postgresql"
    echo ""
    read -p "Press enter to exit..."
    exit 1
fi
echo "✅ PostgreSQL client found"
echo ""

# Check if PostgreSQL server is running
echo "🔍 Checking PostgreSQL server..."
if ! pg_isready -h $DB_HOST -p $DB_PORT &> /dev/null; then
    echo "⚠️  PostgreSQL server not running!"
    echo ""
    echo "Start PostgreSQL:"
    echo "  Ubuntu/Debian: sudo systemctl start postgresql"
    echo "  Docker:        docker-compose up -d"
    echo ""
    read -p "Start with Docker Compose? (y/n): " start_docker
    if [ "$start_docker" = "y" ] || [ "$start_docker" = "Y" ]; then
        if [ -f "docker-compose.yml" ]; then
            docker-compose up -d postgres
            sleep 3
            if ! pg_isready -h $DB_HOST -p $DB_PORT &> /dev/null; then
                echo "❌ Failed to start PostgreSQL"
                exit 1
            fi
            echo "✅ PostgreSQL started via Docker"
        else
            echo "❌ docker-compose.yml not found"
            exit 1
        fi
    else
        exit 1
    fi
else
    echo "✅ PostgreSQL server is running"
fi
echo ""

# Create database and user
echo "📦 Setting up database and user..."
echo ""

# Check if we need sudo for postgres user
PSQL_CMD="psql"
if command -v sudo &> /dev/null && [ -d "/var/run/postgresql" ]; then
    PSQL_CMD="sudo -u postgres psql"
fi

# Drop existing database if it exists (with confirmation)
if $PSQL_CMD -lqt | cut -d \| -f 1 | grep -qw $DB_NAME; then
    echo "⚠️  Database '$DB_NAME' already exists!"
    read -p "Drop and recreate? (y/n): " drop_db
    if [ "$drop_db" = "y" ] || [ "$drop_db" = "Y" ]; then
        echo "Dropping existing database..."
        $PSQL_CMD -c "DROP DATABASE IF EXISTS $DB_NAME;" 2>/dev/null || true
        echo "✅ Database dropped"
    else
        echo "❌ Cannot proceed with existing database"
        exit 1
    fi
fi

# Create user if not exists
echo "Creating user '$DB_USER'..."
$PSQL_CMD -c "CREATE USER $DB_USER WITH PASSWORD '$DB_PASS';" 2>/dev/null || echo "User already exists"

# Create database
echo "Creating database '$DB_NAME'..."
$PSQL_CMD -c "CREATE DATABASE $DB_NAME OWNER $DB_USER;"

# Grant privileges
echo "Granting privileges..."
$PSQL_CMD -c "GRANT ALL PRIVILEGES ON DATABASE $DB_NAME TO $DB_USER;"

echo "✅ Database and user created"
echo ""

# Import backup
echo "📥 Importing backup (this may take a few minutes)..."
echo ""

# Check backup format
BACKUP_FORMAT=$(file "$BACKUP_FILE" | grep -o "PostgreSQL.*dump")
echo "Backup format: $BACKUP_FORMAT"
echo ""

# Try different import methods
if [[ "$BACKUP_FORMAT" == *"custom"* ]]; then
    echo "Using pg_restore with error tolerance..."
    # Use --no-owner and --no-privileges to avoid permission issues
    # Continue on errors as some objects might not be compatible
    PGPASSWORD=$DB_PASS pg_restore \
        -h $DB_HOST \
        -p $DB_PORT \
        -U $DB_USER \
        -d $DB_NAME \
        --no-owner \
        --no-privileges \
        --verbose \
        --exit-on-error \
        "$BACKUP_FILE" 2>&1 | tee /tmp/pg_restore.log | tail -30
    RESTORE_EXIT=${PIPESTATUS[0]}
    
    # If that fails due to version, try without exit-on-error
    if [ $RESTORE_EXIT -ne 0 ]; then
        echo ""
        echo "⚠️  First attempt failed, trying with error tolerance..."
        echo ""
        PGPASSWORD=$DB_PASS pg_restore \
            -h $DB_HOST \
            -p $DB_PORT \
            -U $DB_USER \
            -d $DB_NAME \
            --no-owner \
            --no-privileges \
            --verbose \
            "$BACKUP_FILE" 2>&1 | tee -a /tmp/pg_restore.log | tail -30
        RESTORE_EXIT=${PIPESTATUS[0]}
    fi
else
    # Plain SQL dump
    echo "Using psql for plain SQL dump..."
    PGPASSWORD=$DB_PASS psql \
        -h $DB_HOST \
        -p $DB_PORT \
        -U $DB_USER \
        -d $DB_NAME \
        -f "$BACKUP_FILE" 2>&1 | tail -30
    RESTORE_EXIT=$?
fi

echo ""
if [ $RESTORE_EXIT -eq 0 ]; then
    echo "✅ Backup imported successfully"
else
    echo "⚠️  Import completed with exit code: $RESTORE_EXIT"
    echo "   Check /tmp/pg_restore.log for details"
    echo "   This may be due to version incompatibility or already existing objects"
fi
echo ""

# Create .env.local if it doesn't exist
echo "⚙️  Configuring environment..."
if [ ! -f ".env.local" ]; then
    cp .env.example .env.local
    echo "✅ Created .env.local from .env.example"
else
    echo "✅ .env.local already exists"
fi

# Update DATABASE_URL in .env.local
DATABASE_URL="postgresql://${DB_USER}:${DB_PASS}@${DB_HOST}:${DB_PORT}/${DB_NAME}"
if grep -q "^DATABASE_URL=" .env.local; then
    sed -i "s|^DATABASE_URL=.*|DATABASE_URL=${DATABASE_URL}|" .env.local
    echo "✅ Updated DATABASE_URL in .env.local"
else
    echo "DATABASE_URL=${DATABASE_URL}" >> .env.local
    echo "✅ Added DATABASE_URL to .env.local"
fi
echo ""

# Verify data
echo "🔍 Verifying import..."
TABLE_COUNT=$(PGPASSWORD=$DB_PASS psql -h $DB_HOST -p $DB_PORT -U $DB_USER -d $DB_NAME -t -c "SELECT COUNT(*) FROM information_schema.tables WHERE table_schema = 'public';")
echo "   Tables found: $TABLE_COUNT"

if [ "$TABLE_COUNT" -gt 0 ]; then
    echo ""
    echo "📊 Sample table counts:"
    PGPASSWORD=$DB_PASS psql -h $DB_HOST -p $DB_PORT -U $DB_USER -d $DB_NAME -c "
        SELECT 
            schemaname,
            tablename,
            n_live_tup as row_count
        FROM pg_stat_user_tables
        ORDER BY n_live_tup DESC
        LIMIT 10;
    " 2>/dev/null || echo "   (Table statistics not available yet)"
fi
echo ""

echo "================================================================================"
echo "✅ PostgreSQL Setup Complete!"
echo "================================================================================"
echo ""
echo "Database Details:"
echo "  Host:     $DB_HOST:$DB_PORT"
echo "  Database: $DB_NAME"
echo "  User:     $DB_USER"
echo "  Tables:   $TABLE_COUNT"
echo ""
echo "Connection String:"
echo "  $DATABASE_URL"
echo ""
echo "Next Steps:"
echo "  1. Test connection: psql '$DATABASE_URL'"
echo "  2. Start GUI:       ./start_gui.sh"
echo "  3. Run pipeline:    ./run_pipeline.sh"
echo ""
echo "Configuration saved in .env.local"
echo ""
read -p "Press enter to finish..."
