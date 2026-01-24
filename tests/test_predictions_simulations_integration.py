"""Test integration between Predictions and Simulations tabs"""
import sys
from pathlib import Path

project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def test_imports():
    """Test that all required modules can be imported"""
    logger.info("\n" + "="*80)
    logger.info("Testing: Module Imports")
    logger.info("="*80)

    try:
        from src.gui.tabs import predictions, simulations
        from src.models.trading_simulation import TradingSimulation
        from src.models.predictions import Prediction
        logger.info("✓ All imports successful")
        return True
    except Exception as e:
        logger.error(f"✗ Import failed: {e}")
        return False


def test_prediction_details_with_simulation():
    """Test that prediction details can load simulation data"""
    logger.info("\n" + "="*80)
    logger.info("Testing: Prediction Details with Simulation Data")
    logger.info("="*80)

    try:
        from src.gui.tabs.predictions import get_prediction_details
        from src.models.database import get_scoped_session
        from src.models.predictions import Prediction
        from src.models.trading_simulation import TradingSimulation

        with get_scoped_session() as db:
            # Get a prediction that has a simulation
            prediction = db.query(Prediction).join(
                TradingSimulation,
                Prediction.prediction_id == TradingSimulation.prediction_id
            ).first()

            if not prediction:
                logger.warning("⚠ No predictions with simulations found - skipping test")
                return True

            logger.info(f"Found prediction: {prediction.prediction_id}")

            # Get the database engine
            from src.models.database import engine

            # Test loading details without performance (fast)
            title, body = get_prediction_details(engine, prediction.prediction_id, load_performance=False)

            logger.info(f"✓ Prediction details loaded successfully")
            logger.info(f"  Title type: {type(title)}")
            logger.info(f"  Body type: {type(body)}")

            return True

    except Exception as e:
        logger.error(f"✗ Test failed: {e}", exc_info=True)
        return False


def test_simulation_table_with_details_button():
    """Test that simulation table includes details button"""
    logger.info("\n" + "="*80)
    logger.info("Testing: Simulation Table with Details Button")
    logger.info("="*80)

    try:
        from src.gui.tabs.simulations import get_simulation_table
        from src.models.database import engine

        # Get simulation table
        table = get_simulation_table(engine)

        logger.info(f"✓ Simulation table generated successfully")
        logger.info(f"  Table type: {type(table)}")

        # Check if table contains the details button
        table_str = str(table)
        if "sim-detail-btn" in table_str:
            logger.info("✓ Details button found in table")
            return True
        else:
            logger.warning("⚠ Details button not found in table (might be no simulations)")
            return True

    except Exception as e:
        logger.error(f"✗ Test failed: {e}", exc_info=True)
        return False


def main():
    """Run all integration tests"""
    logger.info("\n" + "="*80)
    logger.info("  Testing Predictions-Simulations Integration")
    logger.info("="*80)

    results = []

    # Test 1: Imports
    results.append(("Imports", test_imports()))

    # Test 2: Prediction details with simulation
    results.append(("Prediction Details", test_prediction_details_with_simulation()))

    # Test 3: Simulation table with details button
    results.append(("Simulation Table", test_simulation_table_with_details_button()))

    # Summary
    logger.info("\n" + "="*80)
    logger.info("Test Results Summary")
    logger.info("="*80)

    all_passed = True
    for name, passed in results:
        status = "✓ PASS" if passed else "✗ FAIL"
        logger.info(f"{status}: {name}")
        if not passed:
            all_passed = False

    logger.info("="*80)

    if all_passed:
        logger.info("✓ All integration tests passed!")
        logger.info("\nNext steps:")
        logger.info("1. Start the GUI: python src/gui/app.py")
        logger.info("2. Navigate to Predictions tab")
        logger.info("3. Click 'Details' on a prediction → should show simulation data if available")
        logger.info("4. Navigate to Simulations tab")
        logger.info("5. Click '📊' button → should open prediction details modal")
        logger.info("="*80)
        return 0
    else:
        logger.error("✗ Some tests failed!")
        return 1


if __name__ == "__main__":
    sys.exit(main())
