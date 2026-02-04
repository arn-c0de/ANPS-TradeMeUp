#!/usr/bin/env python3
"""
Migrate data from SQLite to PostgreSQL
This script copies all data from trademeup.db to PostgreSQL database
"""
import sys
from pathlib import Path
import sqlite3
from datetime import datetime

# Add project root to path
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

import logging
from sqlalchemy import create_engine, text, inspect
from sqlalchemy.orm import sessionmaker

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


def get_sqlite_tables(sqlite_path):
    """Get list of tables from SQLite database"""
    conn = sqlite3.connect(sqlite_path)
    cursor = conn.cursor()
    cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%' AND name != 'alembic_version'")
    tables = [row[0] for row in cursor.fetchall()]
    conn.close()
    return tables


def get_table_count(conn, table_name, is_sqlite=False):
    """Get row count for a table"""
    try:
        if is_sqlite:
            cursor = conn.cursor()
            cursor.execute(f"SELECT COUNT(*) FROM {table_name}")
            return cursor.fetchone()[0]
        else:
            result = conn.execute(text(f'SELECT COUNT(*) FROM "{table_name}"'))
            return result.scalar()
    except Exception as e:
        logger.warning(f"Could not count rows in {table_name}: {e}")
        return 0


def migrate_table(sqlite_conn, postgres_session, table_name):
    """Migrate a single table from SQLite to PostgreSQL"""
    try:
        # Get column names and types from SQLite
        cursor = sqlite_conn.cursor()
        cursor.execute(f"PRAGMA table_info({table_name})")
        table_info = cursor.fetchall()
        columns = [row[1] for row in table_info]
        column_types = {row[1]: row[2] for row in table_info}
        
        # Get PostgreSQL column types
        from sqlalchemy import inspect
        postgres_inspector = inspect(postgres_session.bind)
        postgres_columns = {col['name']: col['type'] for col in postgres_inspector.get_columns(table_name)}
        
        # Get data from SQLite
        cursor.execute(f"SELECT * FROM {table_name}")
        rows = cursor.fetchall()
        
        if not rows:
            logger.info(f"  ✓ {table_name}: No data to migrate")
            return 0, 0
        
        # Insert into PostgreSQL
        inserted = 0
        failed = 0
        
        for row in rows:
            try:
                # Build INSERT query
                placeholders = ', '.join([f':{col}' for col in columns])
                column_names = ', '.join([f'"{col}"' for col in columns])
                query = f'INSERT INTO "{table_name}" ({column_names}) VALUES ({placeholders})'
                
                # Create parameter dict with type conversions
                params = {}
                for col, val in zip(columns, row):
                    # Convert SQLite integers to PostgreSQL booleans
                    if col in postgres_columns:
                        pg_type = str(postgres_columns[col]).upper()
                        if 'BOOLEAN' in pg_type and isinstance(val, int):
                            val = bool(val)
                    params[col] = val
                
                # Execute insert
                postgres_session.execute(text(query), params)
                inserted += 1
                
                # Commit in batches of 100
                if inserted % 100 == 0:
                    postgres_session.commit()
                    logger.info(f"    {table_name}: {inserted} rows inserted...")
                    
            except Exception as e:
                failed += 1
                if failed <= 5:  # Only log first 5 errors
                    logger.warning(f"    Failed to insert row in {table_name}: {e}")
                postgres_session.rollback()
        
        # Final commit
        postgres_session.commit()
        
        logger.info(f"  ✓ {table_name}: {inserted} rows inserted, {failed} failed")
        return inserted, failed
        
    except Exception as e:
        logger.error(f"  ✗ {table_name}: Migration failed - {e}")
        postgres_session.rollback()
        return 0, 0


def main():
    """Main migration function"""
    print("=" * 80)
    print("  TradeMeUp - SQLite to PostgreSQL Migration")
    print("=" * 80)
    print()
    
    # Paths and connections
    sqlite_path = project_root / "trademeup.db"
    
    if not sqlite_path.exists():
        logger.error(f"SQLite database not found: {sqlite_path}")
        return False
    
    logger.info(f"SQLite database: {sqlite_path}")
    
    # Connect to databases
    try:
        # SQLite connection
        sqlite_conn = sqlite3.connect(str(sqlite_path))
        logger.info("✓ Connected to SQLite database")
        
        # PostgreSQL connection
        from src.config.settings import settings
        postgres_engine = create_engine(settings.database_url)
        Session = sessionmaker(bind=postgres_engine)
        postgres_session = Session()
        logger.info("✓ Connected to PostgreSQL database")
        
    except Exception as e:
        logger.error(f"✗ Database connection failed: {e}")
        return False
    
    # Get tables to migrate
    tables = get_sqlite_tables(sqlite_path)
    logger.info(f"\nFound {len(tables)} tables to migrate:")
    
    # Show row counts before migration
    logger.info("\nRow counts before migration:")
    logger.info("-" * 40)
    for table in tables:
        sqlite_count = get_table_count(sqlite_conn, table, is_sqlite=True)
        postgres_count = get_table_count(postgres_session, table, is_sqlite=False)
        logger.info(f"  {table:30} SQLite: {sqlite_count:6d}  PostgreSQL: {postgres_count:6d}")
    
    # Confirm migration
    print("\n" + "=" * 80)
    response = input("Start migration? This will INSERT data into PostgreSQL (y/n): ")
    if response.lower() != 'y':
        logger.info("Migration cancelled by user")
        return False
    
    # Migrate tables
    logger.info("\nStarting migration...")
    logger.info("=" * 80)
    
    total_inserted = 0
    total_failed = 0
    
    for table in tables:
        inserted, failed = migrate_table(sqlite_conn, postgres_session, table)
        total_inserted += inserted
        total_failed += failed
    
    # Show row counts after migration
    logger.info("\nRow counts after migration:")
    logger.info("-" * 40)
    for table in tables:
        sqlite_count = get_table_count(sqlite_conn, table, is_sqlite=True)
        postgres_count = get_table_count(postgres_session, table, is_sqlite=False)
        logger.info(f"  {table:30} SQLite: {sqlite_count:6d}  PostgreSQL: {postgres_count:6d}")
    
    # Summary
    print("\n" + "=" * 80)
    logger.info(f"Migration complete!")
    logger.info(f"  Total inserted: {total_inserted}")
    logger.info(f"  Total failed: {total_failed}")
    print("=" * 80)
    
    # Close connections
    sqlite_conn.close()
    postgres_session.close()
    
    return True


if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)
