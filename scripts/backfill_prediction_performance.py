"""
Backfill Prediction Performance and Simulations

This script:
1. Finds all predictions without performance data (PredictionOutcome)
2. Calculates and saves performance for each prediction
3. Creates trading simulations for predictions without simulations

Run this script to retroactively calculate performance for all historical predictions.
"""

import logging
import sys
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from sqlalchemy import func
from sqlalchemy.orm import Session, joinedload

from src.models.database import engine
from src.models.predictions import Prediction, PredictionOutcome
from src.models.trading_simulation import TradingSimulation
from src.services.prediction_performance_service import PredictionPerformanceService
from src.simulations.trading_simulator import TradingSimulationEngine
from src.utils.activity_logger import activity_logger

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


def backfill_prediction_outcomes(db: Session, limit: int = None) -> dict:
    """
    Calculate and save performance for predictions without outcomes.
    
    Args:
        db: Database session
        limit: Optional limit on number of predictions to process
        
    Returns:
        dict: Statistics about the backfill operation
    """
    logger.info("🔍 Finding predictions without performance data...")

    # Find predictions without outcomes
    query = db.query(Prediction).outerjoin(
        PredictionOutcome,
        Prediction.prediction_id == PredictionOutcome.prediction_id
    ).filter(
        PredictionOutcome.prediction_id.is_(None)
    ).options(
        joinedload(Prediction.entity)
    ).order_by(Prediction.created_at.desc())

    if limit:
        query = query.limit(limit)

    predictions_without_outcomes = query.all()
    total = len(predictions_without_outcomes)

    logger.info(f"📊 Found {total} predictions without performance data")

    if total == 0:
        return {
            'total': 0,
            'processed': 0,
            'success': 0,
            'errors': 0,
            'skipped': 0
        }

    performance_service = PredictionPerformanceService()

    processed = 0
    success = 0
    errors = 0
    skipped = 0

    for i, pred in enumerate(predictions_without_outcomes, 1):
        try:
            entity = pred.entity

            if not entity:
                logger.warning(f"⚠️ Prediction {pred.prediction_id} has no entity, skipping")
                skipped += 1
                continue

            logger.info(f"📈 [{i}/{total}] Calculating performance for {entity.entity_name} ({pred.horizon})...")

            # Calculate performance
            performance = performance_service.get_prediction_performance(pred, entity)

            if performance:
                # Save to database
                performance_service.save_prediction_performance(
                    pred.prediction_id,
                    performance,
                    db
                )
                db.commit()

                total_return = performance.get('total_return_pct', 0)
                is_correct = performance.get('is_correct', False)
                logger.info(f"✅ Saved performance: {total_return:+.2f}% ({'✓' if is_correct else '✗'})")
                success += 1
            else:
                logger.warning("⚠️ Could not calculate performance (may not be tradable)")
                skipped += 1

            processed += 1

        except Exception as e:
            logger.error(f"❌ Error processing prediction {pred.prediction_id}: {e}")
            errors += 1
            processed += 1

    stats = {
        'total': total,
        'processed': processed,
        'success': success,
        'errors': errors,
        'skipped': skipped
    }

    logger.info(f"📊 Performance backfill complete: {success} success, {errors} errors, {skipped} skipped")
    activity_logger.log_activity(
        f"Backfilled {success}/{total} prediction outcomes",
        "INFO"
    )

    return stats


def backfill_simulations(db: Session, limit: int = None) -> dict:
    """
    Create simulations for predictions without simulations.
    
    Args:
        db: Database session
        limit: Optional limit on number of predictions to process
        
    Returns:
        dict: Statistics about the backfill operation
    """
    logger.info("🔍 Finding predictions without simulations...")

    # Find predictions without simulations
    query = db.query(Prediction).outerjoin(
        TradingSimulation,
        Prediction.prediction_id == TradingSimulation.prediction_id
    ).filter(
        TradingSimulation.prediction_id.is_(None)
    ).options(
        joinedload(Prediction.entity)
    ).order_by(Prediction.created_at.desc())

    if limit:
        query = query.limit(limit)

    predictions_without_sims = query.all()
    total = len(predictions_without_sims)

    logger.info(f"🧪 Found {total} predictions without simulations")

    if total == 0:
        return {
            'total': 0,
            'processed': 0,
            'created': 0,
            'errors': 0,
            'skipped': 0
        }

    sim_engine = TradingSimulationEngine()

    processed = 0
    created = 0
    errors = 0
    skipped = 0

    for i, pred in enumerate(predictions_without_sims, 1):
        try:
            entity = pred.entity

            if not entity:
                logger.warning(f"⚠️ Prediction {pred.prediction_id} has no entity, skipping")
                skipped += 1
                continue

            logger.info(f"🧪 [{i}/{total}] Creating simulation for {entity.entity_name} ({pred.horizon})...")

            # Create simulation
            simulation = sim_engine.simulate_prediction(db, pred, entity)

            if simulation:
                db.commit()

                decision = simulation.decision
                expected_return = simulation.expected_return_pct or 0
                risk_score = simulation.risk_score or 0
                logger.info(f"✅ Created simulation: {decision.upper()} (Return: {expected_return:+.2f}%, Risk: {risk_score:.2f})")
                created += 1
            else:
                logger.warning("⚠️ Simulation not created (may not meet criteria)")
                skipped += 1

            processed += 1

        except Exception as e:
            logger.error(f"❌ Error creating simulation for {pred.prediction_id}: {e}")
            errors += 1
            processed += 1

    stats = {
        'total': total,
        'processed': processed,
        'created': created,
        'errors': errors,
        'skipped': skipped
    }

    logger.info(f"🧪 Simulation backfill complete: {created} created, {errors} errors, {skipped} skipped")
    activity_logger.log_activity(
        f"Backfilled {created}/{total} trading simulations",
        "INFO"
    )

    return stats


def main():
    """Main execution function"""
    logger.info("=" * 80)
    logger.info("🚀 Starting Prediction Performance & Simulation Backfill")
    logger.info("=" * 80)

    try:
        with Session(engine) as db:
            # Get total counts
            total_predictions = db.query(func.count(Prediction.prediction_id)).scalar() or 0
            total_outcomes = db.query(func.count(PredictionOutcome.outcome_id)).scalar() or 0
            total_simulations = db.query(func.count(TradingSimulation.simulation_id)).scalar() or 0

            logger.info("📊 Current Status:")
            logger.info(f"   - Total Predictions: {total_predictions}")
            logger.info(f"   - Total Outcomes: {total_outcomes}")
            logger.info(f"   - Total Simulations: {total_simulations}")
            logger.info("")

            # Step 1: Backfill prediction outcomes
            logger.info("=" * 80)
            logger.info("STEP 1: Backfill Prediction Outcomes")
            logger.info("=" * 80)
            outcome_stats = backfill_prediction_outcomes(db)
            logger.info("")

            # Step 2: Backfill simulations
            logger.info("=" * 80)
            logger.info("STEP 2: Backfill Trading Simulations")
            logger.info("=" * 80)
            sim_stats = backfill_simulations(db)
            logger.info("")

            # Final summary
            logger.info("=" * 80)
            logger.info("✅ BACKFILL COMPLETE")
            logger.info("=" * 80)
            logger.info(f"📊 Outcomes: {outcome_stats['success']}/{outcome_stats['total']} calculated")
            logger.info(f"🧪 Simulations: {sim_stats['created']}/{sim_stats['total']} created")
            logger.info("")

            # New totals
            new_total_outcomes = db.query(func.count(PredictionOutcome.outcome_id)).scalar() or 0
            new_total_simulations = db.query(func.count(TradingSimulation.simulation_id)).scalar() or 0

            logger.info("📈 New Status:")
            logger.info(f"   - Total Predictions: {total_predictions}")
            logger.info(f"   - Total Outcomes: {new_total_outcomes} (+{new_total_outcomes - total_outcomes})")
            logger.info(f"   - Total Simulations: {new_total_simulations} (+{new_total_simulations - total_simulations})")

            logger.info("=" * 80)

    except Exception as e:
        logger.error(f"❌ Fatal error during backfill: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()
