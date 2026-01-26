"""
Manually apply stop loss and take profit fields migration to database.

This script adds the new columns to the trading_simulations table without using Alembic.
Useful for quick updates during development.
"""
import sys
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from sqlalchemy import text
from src.models.database import engine
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def apply_migration():
    """Apply the stop loss and take profit migration."""
    try:
        with engine.connect() as conn:
            logger.info("Starting migration: add stop loss and take profit fields")
            
            # Check if columns already exist (SQLite-compatible)
            try:
                result = conn.execute(text("PRAGMA table_info(trading_simulations)"))
                columns = [row[1] for row in result.fetchall()]  # column name is at index 1
                
                if 'stop_loss_price' in columns:
                    logger.info("Migration already applied - columns exist")
                    return
            except Exception as e:
                logger.warning(f"Could not check existing columns: {e}")
            
            # Add stop loss fields (SQLite doesn't support IF NOT EXISTS in ALTER TABLE)
            logger.info("Adding stop_loss_price column...")
            conn.execute(text(
                "ALTER TABLE trading_simulations ADD COLUMN stop_loss_price FLOAT"
            ))
            
            logger.info("Adding stop_loss_pct column...")
            conn.execute(text(
                "ALTER TABLE trading_simulations ADD COLUMN stop_loss_pct FLOAT"
            ))
            
            logger.info("Adding stop_loss_type column...")
            conn.execute(text(
                "ALTER TABLE trading_simulations ADD COLUMN stop_loss_type VARCHAR(20)"
            ))
            
            logger.info("Adding trailing_stop_price column...")
            conn.execute(text(
                "ALTER TABLE trading_simulations ADD COLUMN trailing_stop_price FLOAT"
            ))
            
            # Add take profit fields
            logger.info("Adding take_profit_price column...")
            conn.execute(text(
                "ALTER TABLE trading_simulations ADD COLUMN take_profit_price FLOAT"
            ))
            
            logger.info("Adding take_profit_pct column...")
            conn.execute(text(
                "ALTER TABLE trading_simulations ADD COLUMN take_profit_pct FLOAT"
            ))
            
            logger.info("Adding risk_reward_ratio column...")
            conn.execute(text(
                "ALTER TABLE trading_simulations ADD COLUMN risk_reward_ratio FLOAT"
            ))
            
            # Add exit strategy JSON field
            logger.info("Adding exit_strategy column...")
            conn.execute(text(
                "ALTER TABLE trading_simulations ADD COLUMN exit_strategy JSON"
            ))
            
            # Create index (IF NOT EXISTS is supported for CREATE INDEX)
            logger.info("Creating index on stop_loss_type...")
            conn.execute(text(
                "CREATE INDEX IF NOT EXISTS idx_simulation_stop_loss_type ON trading_simulations(stop_loss_type)"
            ))
            
            conn.commit()
            logger.info("✅ Migration completed successfully!")
            
    except Exception as e:
        logger.error(f"❌ Migration failed: {e}")
        raise


def rollback_migration():
    """Rollback the stop loss and take profit migration."""
    try:
        with engine.connect() as conn:
            logger.info("Rolling back migration: remove stop loss and take profit fields")
            
            # Drop index
            logger.info("Dropping index...")
            conn.execute(text(
                "DROP INDEX IF EXISTS idx_simulation_stop_loss_type"
            ))
            
            # Drop columns
            columns = [
                'exit_strategy',
                'risk_reward_ratio',
                'take_profit_pct',
                'take_profit_price',
                'trailing_stop_price',
                'stop_loss_type',
                'stop_loss_pct',
                'stop_loss_price'
            ]
            
            for column in columns:
                logger.info(f"Dropping {column} column...")
                conn.execute(text(
                    f"ALTER TABLE trading_simulations DROP COLUMN IF EXISTS {column}"
                ))
            
            conn.commit()
            logger.info("✅ Rollback completed successfully!")
            
    except Exception as e:
        logger.error(f"❌ Rollback failed: {e}")
        raise


if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(description="Apply stop loss migration")
    parser.add_argument(
        "--rollback",
        action="store_true",
        help="Rollback the migration instead of applying it"
    )
    
    args = parser.parse_args()
    
    if args.rollback:
        confirmation = input("⚠️  Are you sure you want to rollback? This will remove all stop loss data. (yes/no): ")
        if confirmation.lower() == "yes":
            rollback_migration()
        else:
            logger.info("Rollback cancelled")
    else:
        apply_migration()
