"""Test script to run trading simulation on existing predictions"""
import sys
from pathlib import Path

project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

import logging

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


def main():
    """Test trading simulation agent"""
    logger.info("=" * 80)
    logger.info("  Testing Trading Simulation Agent")
    logger.info("=" * 80)
    
    try:
        from src.agents.trading_simulation_agent import TradingSimulationAgent
        
        # Create agent
        logger.info("\nCreating trading simulation agent...")
        agent = TradingSimulationAgent()
        
        # Get current statistics
        logger.info("\nCurrent simulation statistics:")
        stats = agent.get_statistics()
        logger.info(f"  - Total simulations: {stats.get('total_simulations', 0)}")
        logger.info(f"  - Buys: {stats.get('buys', 0)}")
        logger.info(f"  - Sells: {stats.get('sells', 0)}")
        logger.info(f"  - Holds: {stats.get('holds', 0)}")
        
        # Process batch
        logger.info("\nProcessing batch of predictions (limit=20, last 7 days)...")
        results = agent.process_batch(limit=20, lookback_days=7)
        
        logger.info("\nResults:")
        logger.info(f"  - Processed: {results.get('processed', 0)}")
        logger.info(f"  - Created: {results.get('created', 0)}")
        logger.info(f"  - Updated: {results.get('updated', 0)}")
        logger.info(f"  - Skipped: {results.get('skipped', 0)}")
        logger.info(f"  - Errors: {results.get('errors', 0)}")
        
        # Get updated statistics
        logger.info("\nUpdated simulation statistics:")
        stats = agent.get_statistics()
        logger.info(f"  - Total simulations: {stats.get('total_simulations', 0)}")
        logger.info(f"  - Buys: {stats.get('buys', 0)}")
        logger.info(f"  - Sells: {stats.get('sells', 0)}")
        logger.info(f"  - Holds: {stats.get('holds', 0)}")
        
        logger.info("\n" + "=" * 80)
        logger.info("✓ Trading simulation test complete!")
        logger.info("=" * 80)
        
    except Exception as e:
        logger.error(f"✗ Test failed: {e}", exc_info=True)
        sys.exit(1)


if __name__ == "__main__":
    main()
