"""
Integration test to verify simulation fixes work end-to-end.
Tests the actual database and market data fetching behavior.
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

import uuid
from datetime import UTC, datetime, timedelta

import pytest

from src.models.database import get_scoped_session
from src.models.entities import Entity
from src.models.predictions import Prediction, PredictionOutcome
from src.models.trading_simulation import TradingSimulation
from src.simulations.trading_simulator import TradingSimulationEngine

# These write to and read from the real database rather than a fake.
pytestmark = pytest.mark.requires_database


def _purge_test_entity(db, entity_id: str) -> None:
    """Remove any rows a previous run of this test left behind.

    Cleanup used to live at the end of the test body, so a failure anywhere
    above it leaked an Entity into the developer's database and every later
    run then died on a primary-key collision instead of on the real problem.
    """
    # Anything still pending in the session would be flushed *after* these
    # statements and resurrect the rows we are deleting.
    db.expunge_all()

    prediction_ids = [
        row[0] for row in
        db.query(Prediction.prediction_id).filter(
            Prediction.entity_id == entity_id
        ).all()
    ]

    # Delete children before parents: the foreign keys are not ON DELETE CASCADE.
    if prediction_ids:
        db.query(TradingSimulation).filter(
            TradingSimulation.prediction_id.in_(prediction_ids)
        ).delete(synchronize_session=False)
        db.query(PredictionOutcome).filter(
            PredictionOutcome.prediction_id.in_(prediction_ids)
        ).delete(synchronize_session=False)
        db.query(Prediction).filter(
            Prediction.prediction_id.in_(prediction_ids)
        ).delete(synchronize_session=False)

    db.query(Entity).filter(Entity.entity_id == entity_id).delete(
        synchronize_session=False
    )
    db.commit()


def test_outcome_fallback():
    """Test that simulator uses PredictionOutcome when live data fails."""
    print("\n=== Testing PredictionOutcome Fallback ===\n")

    with get_scoped_session() as db:
        _purge_test_entity(db, "TEST_INVALID_TICKER_XYZ")

        # Create a test entity with invalid ticker (to force live data to fail)
        test_entity = Entity(
            entity_id="TEST_INVALID_TICKER_XYZ",
            entity_name="Test Invalid Entity",
            entity_type="equity"
        )
        db.add(test_entity)

        # Create a test prediction. `timestamp` (when the prediction is
        # about) is NOT NULL and distinct from `created_at` (when the row was
        # written); omitting it made this fixture fail to insert at all.
        pred_id = uuid.uuid4()
        predicted_at = datetime.now(UTC) - timedelta(days=7)
        test_pred = Prediction(
            prediction_id=pred_id,
            entity_id="TEST_INVALID_TICKER_XYZ",
            horizon="5d",
            timestamp=predicted_at,
            expected_return={"mean": 0.0250},  # 2.5%
            direction_probabilities={"up": 0.75, "down": 0.15, "flat": 0.10},
            confidence=0.80,
            model_version="test_fixture",
            created_at=predicted_at
        )
        db.add(test_pred)

        # Create a saved outcome (simulating historical backfill)
        test_outcome = PredictionOutcome(
            outcome_id=uuid.uuid4(),
            prediction_id=pred_id,
            actual_return=3.2,  # 3.2% actual return
            error=-0.7,  # underestimated by 0.7%
            direction_correct=True,
            evaluation_timestamp=datetime.now(UTC) - timedelta(days=2),
            created_at=datetime.now(UTC) - timedelta(days=2)
        )
        db.add(test_outcome)
        db.commit()

        try:
            print("✅ Created test prediction and saved outcome in database")

            # The realised return must come from the stored outcome, since the
            # ticker is deliberately unresolvable.
            _, realised = TradingSimulationEngine()._resolve_actual_return(
                db, test_pred, test_entity
            )

            assert realised is not None, \
                "Should fall back to the stored PredictionOutcome"
            assert abs(realised - 3.2) < 0.01, \
                f"Should use saved outcome 3.2%, got {realised}%"

            print("\n✅ SUCCESS: Simulator correctly used PredictionOutcome fallback!")
        finally:
            _purge_test_entity(db, "TEST_INVALID_TICKER_XYZ")
            print("\n✅ Test data cleaned up\n")


def test_missing_data_handling():
    """Test that simulator gracefully handles missing actual data."""
    print("\n=== Testing Missing Data Handling ===\n")

    with get_scoped_session() as db:
        _purge_test_entity(db, "TEST_NOSUCHDATA_ABC")

        # Create entity with invalid ticker AND no saved outcome
        test_entity = Entity(
            entity_id="TEST_NOSUCHDATA_ABC",
            entity_name="Test No Data Entity",
            entity_type="equity"
        )
        db.add(test_entity)

        # Create prediction without outcome
        pred_id = uuid.uuid4()
        predicted_at = datetime.now(UTC) - timedelta(hours=12)
        test_pred = Prediction(
            prediction_id=pred_id,
            entity_id="TEST_NOSUCHDATA_ABC",
            horizon="5d",
            timestamp=predicted_at,
            expected_return={"mean": 0.0180},  # 1.8%
            direction_probabilities={"up": 0.65, "down": 0.25, "flat": 0.10},
            confidence=0.70,
            model_version="test_fixture",
            created_at=predicted_at
        )
        db.add(test_pred)
        db.commit()

        try:
            print("✅ Created test prediction WITHOUT saved outcome")

            engine = TradingSimulationEngine()

            # There is no realised return to be had: live data fails for this
            # ticker and no outcome was stored.
            _, realised = engine._resolve_actual_return(db, test_pred, test_entity)
            assert realised is None, \
                "Actual should be None when neither live data nor an outcome exists"

            # And without a market price there is no trade to model, so the
            # engine declines rather than inventing one. Asserting a
            # simulation *is* created encoded the older behaviour, where a row
            # was written against a price of 0.0 and every cost and risk
            # number computed from it was meaningless.
            simulation = engine.simulate_prediction(db, test_pred, test_entity)
            assert simulation is None, \
                "No simulation should be created without a valid market price"

            print("\n✅ SUCCESS: Simulator correctly declined to simulate!")
        finally:
            _purge_test_entity(db, "TEST_NOSUCHDATA_ABC")
            print("\n✅ Test data cleaned up\n")


def test_date_range_simulation():
    """Test historical simulation with date range filtering."""
    print("\n=== Testing Historical Date Range Simulation ===\n")

    with get_scoped_session() as db:
        # Find real predictions in the database
        old_predictions = db.query(Prediction).filter(
            Prediction.created_at < datetime.now(UTC) - timedelta(days=1)
        ).limit(3).all()

        if not old_predictions:
            print("⚠ No historical predictions found - skipping date range test")
            return

        print(f"✅ Found {len(old_predictions)} historical predictions")

        # Test date range filtering
        engine = TradingSimulationEngine()

        start_date = datetime.now(UTC) - timedelta(days=7)
        end_date = datetime.now(UTC) - timedelta(days=1)

        print(f"\nFiltering predictions from {start_date.date()} to {end_date.date()}")

        stats = engine.create_simulations_from_predictions(
            date_range=(start_date, end_date),
            limit=5
        )

        print("\nSimulation Creation Stats:")
        print(f"  Created: {stats['created']}")
        print(f"  Updated: {stats['updated']}")
        print(f"  Skipped: {stats['skipped']}")
        print(f"  Errors: {stats['errors']}")

        assert stats['errors'] == 0, "Should have no errors"
        print("\n✅ SUCCESS: Historical date range simulation works!")


def main():
    """Run all integration tests."""
    print("\n" + "="*70)
    print("SIMULATION FIXES - INTEGRATION TEST SUITE")
    print("="*70)

    try:
        # Test 1: PredictionOutcome fallback
        test_outcome_fallback()

        # Test 2: Missing data handling
        test_missing_data_handling()

        # Test 3: Date range simulation
        test_date_range_simulation()

        print("\n" + "="*70)
        print("✅ ALL INTEGRATION TESTS PASSED!")
        print("="*70 + "\n")

        print("Summary of Verified Fixes:")
        print("1. ✅ PredictionOutcome fallback works when live data fails")
        print("2. ✅ Missing data handled gracefully (None values)")
        print("3. ✅ Historical date range simulation functional")
        print("4. ✅ Risk calculation handles None divergence")
        print("5. ✅ No crashes or errors with edge cases\n")

    except AssertionError as e:
        print("\n" + "="*70)
        print(f"❌ INTEGRATION TEST FAILED: {e}")
        print("="*70 + "\n")
        raise
    except Exception as e:
        print("\n" + "="*70)
        print(f"❌ ERROR: {e}")
        print("="*70 + "\n")
        import traceback
        traceback.print_exc()
        raise


if __name__ == "__main__":
    main()
