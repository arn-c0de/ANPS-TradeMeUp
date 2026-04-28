#!/usr/bin/env python3
"""Initialize the database schema."""

from pathlib import Path
import sys

PROJECT_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(PROJECT_ROOT))

import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def init_database():
    """Create all database tables"""
    logger.info("Creating database tables...")
    
    try:
        # Import after adding to path
        from src.models.database import engine, Base
        # Import models to register them
        from src.models import (
            raw_news,
            processed_news,
            data_quality,
            entities,
            analysis,
            predictions,
            trading_simulation,
            chart_overlays,
        )
        
        # Create all tables
        Base.metadata.create_all(bind=engine)
        logger.info("✓ All database tables created successfully!")
        
        # Print created tables
        logger.info("\nCreated tables:")
        for table in Base.metadata.sorted_tables:
            logger.info(f"  - {table.name}")
        
        return True
    except Exception as e:
        logger.error(f"✗ Error creating database tables: {e}", exc_info=True)
        return False


if __name__ == "__main__":
    print("=" * 80)
    print("  TradeMeUp - Database Initialization")
    print("=" * 80)
    print()
    
    success = init_database()
    
    print()
    if success:
        print("✓ Database initialization complete!")
        print("  You can now run the pipeline or backfill script.")
    else:
        print("✗ Database initialization failed!")
        print("  Check the error messages above.")
        sys.exit(1)
