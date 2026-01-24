"""Add trading_simulations table directly to database"""
import sys
from pathlib import Path

project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def add_trading_simulations_table():
    """Add trading_simulations table to existing database"""
    logger.info("Adding trading_simulations table...")
    
    try:
        from src.models.database import engine
        from sqlalchemy import text
        
        # Create trading_simulations table using raw SQL
        sql = """
        CREATE TABLE IF NOT EXISTS trading_simulations (
            simulation_id CHAR(36) NOT NULL,
            prediction_id CHAR(36) NOT NULL,
            entity_id VARCHAR(50) NOT NULL,
            horizon VARCHAR(10) NOT NULL,
            decision VARCHAR(10) NOT NULL,
            expected_return_pct FLOAT,
            actual_return_pct FLOAT,
            divergence_pct FLOAT,
            risk_score FLOAT,
            confidence FLOAT,
            calibrated_confidence FLOAT,
            transaction_cost_bps FLOAT,
            cost_breakdown TEXT,
            risk_breakdown TEXT,
            simulation_metadata TEXT,
            created_at DATETIME NOT NULL,
            PRIMARY KEY (simulation_id),
            FOREIGN KEY (prediction_id) REFERENCES predictions(prediction_id),
            FOREIGN KEY (entity_id) REFERENCES entities(entity_id)
        );
        
        CREATE INDEX IF NOT EXISTS idx_simulation_prediction ON trading_simulations(prediction_id);
        CREATE INDEX IF NOT EXISTS idx_simulation_entity_time ON trading_simulations(entity_id, created_at);
        CREATE INDEX IF NOT EXISTS idx_simulation_decision ON trading_simulations(decision, created_at);
        """
        
        with engine.connect() as conn:
            conn.execute(text(sql))
            conn.commit()
        
        logger.info("✓ trading_simulations table created successfully!")
        return True
    except Exception as e:
        logger.error(f"✗ Error creating table: {e}", exc_info=True)
        return False


if __name__ == "__main__":
    print("=" * 80)
    print("  TradeMeUp - Add Trading Simulations Table")
    print("=" * 80)
    print()
    
    success = add_trading_simulations_table()
    
    print()
    if success:
        print("✓ Table created successfully!")
        print("  You can now run the pipeline with simulation support.")
    else:
        print("✗ Table creation failed!")
        print("  Check the error messages above.")
        sys.exit(1)
