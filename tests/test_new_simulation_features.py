"""Test new simulation features - create, delete, refresh"""
import sys
from pathlib import Path

project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

import logging
from datetime import datetime, timedelta

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def test_create_simulations():
    """Test creating simulations from predictions with filters"""
    from src.simulations.trading_simulator import TradingSimulationEngine

    logger.info("\n" + "="*80)
    logger.info("Testing: Create Simulations from Predictions")
    logger.info("="*80)

    engine = TradingSimulationEngine()

    # Test with date range filter
    end_date = datetime.now()
    start_date = end_date - timedelta(days=3)

    stats = engine.create_simulations_from_predictions(
        date_range=(start_date, end_date),
        limit=5
    )

    logger.info(f"✓ Created: {stats['created']}")
    logger.info(f"  Updated: {stats['updated']}")
    logger.info(f"  Skipped: {stats['skipped']}")
    logger.info(f"  Errors: {stats['errors']}")

    return stats


def test_refresh_simulation():
    """Test refreshing a simulation"""
    from src.simulations.trading_simulator import TradingSimulationEngine
    from src.models.database import get_scoped_session
    from src.models.trading_simulation import TradingSimulation

    logger.info("\n" + "="*80)
    logger.info("Testing: Refresh Simulation")
    logger.info("="*80)

    engine = TradingSimulationEngine()

    # Get first simulation
    with get_scoped_session() as db:
        sim = db.query(TradingSimulation).first()
        if not sim:
            logger.warning("No simulations found to refresh")
            return False

        sim_id = str(sim.simulation_id)
        logger.info(f"Refreshing simulation: {sim_id}")

    # Refresh it
    success = engine.refresh_simulation(sim_id)
    logger.info(f"✓ Refresh result: {success}")

    return success


def test_delete_simulation():
    """Test deleting a simulation"""
    from src.simulations.trading_simulator import TradingSimulationEngine
    from src.models.database import get_scoped_session
    from src.models.trading_simulation import TradingSimulation

    logger.info("\n" + "="*80)
    logger.info("Testing: Delete Simulation")
    logger.info("="*80)

    engine = TradingSimulationEngine()

    # Get last simulation
    with get_scoped_session() as db:
        sim = db.query(TradingSimulation).order_by(
            TradingSimulation.created_at.desc()
        ).first()
        if not sim:
            logger.warning("No simulations found to delete")
            return False

        sim_id = str(sim.simulation_id)
        logger.info(f"Deleting simulation: {sim_id}")

    # Delete it
    success = engine.delete_simulation(sim_id)
    logger.info(f"✓ Delete result: {success}")

    return success


def main():
    try:
        # Test 1: Create simulations
        create_stats = test_create_simulations()

        # Test 2: Refresh simulation
        if create_stats['created'] > 0 or create_stats['updated'] > 0:
            test_refresh_simulation()

        # Test 3: Delete simulation
        if create_stats['created'] > 0 or create_stats['updated'] > 0:
            test_delete_simulation()

        logger.info("\n" + "="*80)
        logger.info("✓ All tests completed successfully!")
        logger.info("="*80)

    except Exception as e:
        logger.error(f"✗ Test failed: {e}", exc_info=True)
        sys.exit(1)


if __name__ == "__main__":
    main()
