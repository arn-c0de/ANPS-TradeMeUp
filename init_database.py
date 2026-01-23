#!/usr/bin/env python3
"""
Initialize Database - Create all tables
Run this before starting the pipeline for the first time
"""
import sys
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

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
        from src.models import raw_news, processed_news, data_quality, entities, analysis, predictions
        
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
