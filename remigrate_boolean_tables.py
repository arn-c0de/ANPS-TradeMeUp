#!/usr/bin/env python3
"""
Re-migrate specific tables with boolean conversion
"""
import sys
from pathlib import Path
import sqlite3

project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

import logging
from sqlalchemy import create_engine, text, inspect
from sqlalchemy.orm import sessionmaker

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def migrate_table_with_boolean_conversion(sqlite_conn, postgres_session, table_name):
    """Migrate a table with proper boolean conversion"""
    try:
        # Get column info from SQLite
        cursor = sqlite_conn.cursor()
        cursor.execute(f"PRAGMA table_info({table_name})")
        table_info = cursor.fetchall()
        columns = [row[1] for row in table_info]
        
        # Get PostgreSQL column types
        postgres_inspector = inspect(postgres_session.bind)
        postgres_columns = {col['name']: col['type'] for col in postgres_inspector.get_columns(table_name)}
        
        # Get data from SQLite
        cursor.execute(f"SELECT * FROM {table_name}")
        rows = cursor.fetchall()
        
        if not rows:
            logger.info(f"  ✓ {table_name}: No data to migrate")
            return 0, 0
        
        inserted = 0
        failed = 0
        
        for row in rows:
            try:
                placeholders = ', '.join([f':{col}' for col in columns])
                column_names = ', '.join([f'"{col}"' for col in columns])
                query = f'INSERT INTO "{table_name}" ({column_names}) VALUES ({placeholders})'
                
                # Type conversion
                params = {}
                for col, val in zip(columns, row):
                    if col in postgres_columns:
                        pg_type = str(postgres_columns[col]).upper()
                        if 'BOOLEAN' in pg_type and isinstance(val, int):
                            val = bool(val)
                    params[col] = val
                
                postgres_session.execute(text(query), params)
                inserted += 1
                
                if inserted % 100 == 0:
                    postgres_session.commit()
                    logger.info(f"    {table_name}: {inserted} rows inserted...")
                    
            except Exception as e:
                failed += 1
                if failed <= 3:
                    logger.warning(f"    Failed: {e}")
                postgres_session.rollback()
        
        postgres_session.commit()
        logger.info(f"  ✓ {table_name}: {inserted} inserted, {failed} failed")
        return inserted, failed
        
    except Exception as e:
        logger.error(f"  ✗ {table_name}: {e}")
        postgres_session.rollback()
        return 0, 0


def main():
    sqlite_path = project_root / "trademeup.db"
    
    sqlite_conn = sqlite3.connect(str(sqlite_path))
    
    from src.config.settings import settings
    postgres_engine = create_engine(settings.database_url)
    Session = sessionmaker(bind=postgres_engine)
    postgres_session = Session()
    
    logger.info("Migrating tables with boolean conversion...")
    
    for table in ['prediction_outcomes', 'chart_overlays']:
        migrate_table_with_boolean_conversion(sqlite_conn, postgres_session, table)
    
    sqlite_conn.close()
    postgres_session.close()
    
    logger.info("Done!")


if __name__ == "__main__":
    main()
