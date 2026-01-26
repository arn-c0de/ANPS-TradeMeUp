"""
Resimulate All Trading Simulations

This script:
1. Finds all existing trading simulations
2. Recalculates each simulation with updated parameters (e.g., corrected portfolio size)
3. Updates the database with new values

Run this script to recalculate all simulations after parameter changes (e.g., portfolio size correction).
"""

import sys
import logging
from pathlib import Path
from datetime import datetime

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from sqlalchemy.orm import Session, joinedload
from sqlalchemy import func

from src.models.database import engine
from src.models.predictions import Prediction
from src.models.trading_simulation import TradingSimulation
from src.models.entities import Entity
from src.simulations.trading_simulator import TradingSimulationEngine
from src.utils.activity_logger import activity_logger

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


def resimulate_all(db: Session, limit: int = None) -> dict:
    """
    Recalculate all existing trading simulations.
    
    Args:
        db: Database session
        limit: Optional limit on number of simulations to process
        
    Returns:
        dict: Statistics about the resimulation operation
    """
    logger.info("🔍 Finding all existing trading simulations...")
    
    # Find all simulations with their predictions and entities
    query = db.query(TradingSimulation).join(
        Prediction,
        TradingSimulation.prediction_id == Prediction.prediction_id
    ).options(
        joinedload(TradingSimulation.prediction).joinedload(Prediction.entity)
    ).order_by(TradingSimulation.created_at.desc())
    
    if limit:
        query = query.limit(limit)
    
    simulations = query.all()
    total = len(simulations)
    
    logger.info(f"🧪 Found {total} simulations to recalculate")
    
    if total == 0:
        return {
            'total': 0,
            'processed': 0,
            'updated': 0,
            'errors': 0,
            'skipped': 0
        }
    
    sim_engine = TradingSimulationEngine()
    
    processed = 0
    updated = 0
    errors = 0
    skipped = 0
    
    for i, sim in enumerate(simulations, 1):
        try:
            prediction = sim.prediction
            entity = prediction.entity if prediction else None
            
            if not prediction:
                logger.warning(f"⚠️ Simulation {sim.simulation_id} has no prediction, skipping")
                skipped += 1
                continue
            
            if not entity:
                logger.warning(f"⚠️ Simulation {sim.simulation_id} has no entity, skipping")
                skipped += 1
                continue
            
            entity_name = entity.entity_name if entity else "Unknown"
            horizon = prediction.horizon if prediction else "Unknown"
            
            logger.info(f"🔄 [{i}/{total}] Resimulating {entity_name} ({horizon})...")
            
            # Recalculate simulation
            updated_simulation = sim_engine.simulate_prediction(db, prediction, entity)
            
            if updated_simulation:
                db.commit()
                
                decision = updated_simulation.decision
                expected_return = updated_simulation.expected_return_pct or 0
                risk_score = updated_simulation.risk_score or 0
                position_value = updated_simulation.position_value_usd or 0
                
                logger.info(
                    f"✅ Updated simulation: {decision.upper()} "
                    f"(Return: {expected_return:+.2f}%, Risk: {risk_score:.2f}, "
                    f"Position: ${position_value:.2f})"
                )
                updated += 1
            else:
                logger.warning(f"⚠️ Simulation not updated (may not meet criteria)")
                skipped += 1
            
            processed += 1
            
        except Exception as e:
            logger.error(f"❌ Error resimulating {sim.simulation_id}: {e}")
            import traceback
            traceback.print_exc()
            errors += 1
            processed += 1
    
    stats = {
        'total': total,
        'processed': processed,
        'updated': updated,
        'errors': errors,
        'skipped': skipped
    }
    
    logger.info(f"🔄 Resimulation complete: {updated} updated, {errors} errors, {skipped} skipped")
    activity_logger.log_activity(
        f"Resimulated {updated}/{total} trading simulations",
        "INFO"
    )
    
    return stats


def main():
    """Main execution function"""
    logger.info("=" * 80)
    logger.info("🔄 Starting Trading Simulation Resimulation")
    logger.info("=" * 80)
    
    try:
        with Session(engine) as db:
            # Get total counts
            total_simulations = db.query(func.count(TradingSimulation.simulation_id)).scalar() or 0
            
            logger.info(f"📊 Current Status:")
            logger.info(f"   - Total Simulations: {total_simulations}")
            logger.info("")
            
            # Resimulate all
            logger.info("=" * 80)
            logger.info("STEP 1: Resimulate All Trading Simulations")
            logger.info("=" * 80)
            stats = resimulate_all(db)
            logger.info("")
            
            # Final summary
            logger.info("=" * 80)
            logger.info("✅ RESIMULATION COMPLETE")
            logger.info("=" * 80)
            logger.info(f"🔄 Simulations: {stats['updated']}/{stats['total']} updated")
            logger.info(f"   - Processed: {stats['processed']}")
            logger.info(f"   - Updated: {stats['updated']}")
            logger.info(f"   - Errors: {stats['errors']}")
            logger.info(f"   - Skipped: {stats['skipped']}")
            logger.info("")
            
            logger.info("=" * 80)
            
    except Exception as e:
        logger.error(f"❌ Fatal error during resimulation: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()
