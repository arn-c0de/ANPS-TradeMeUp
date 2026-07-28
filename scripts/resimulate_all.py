"""
Resimulate All Trading Simulations

This script:
1. Finds all existing trading simulations
2. Recalculates each simulation with updated parameters (e.g., corrected portfolio size)
3. Updates the database with new values

Run this script to recalculate all simulations after parameter changes (e.g., portfolio size correction).

Supports parallel processing with --workers flag to speed up execution.
Optimized for PostgreSQL with true concurrent database operations.
"""

import sys
import logging
import argparse
from pathlib import Path
from datetime import datetime
from concurrent.futures import ThreadPoolExecutor, as_completed
from threading import Lock
import os

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from sqlalchemy.orm import Session, joinedload
from sqlalchemy import func

from src.models.database import engine, get_scoped_session
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

# Thread-safe lock for progress tracking
progress_lock = Lock()


def _resimulate_single(sim_data: tuple) -> dict:
    """
    Worker function to resimulate a single trading simulation.
    
    This function is designed to be called by ThreadPoolExecutor workers.
    Each worker creates its own database session and TradingSimulationEngine instance.
    
    With PostgreSQL, database operations can happen truly in parallel, providing
    significant performance improvements over SQLite.
    
    Args:
        sim_data: Tuple of (simulation_id, prediction_id, entity_id, entity_name, horizon, index, total)
        
    Returns:
        dict: Statistics for this simulation {
            'processed': 1,
            'updated': 0 or 1,
            'errors': 0 or 1,
            'skipped': 0 or 1
        }
    """
    sim_id, pred_id, entity_id, entity_name, horizon, index, total = sim_data
    
    stats = {
        'processed': 0,
        'updated': 0,
        'errors': 0,
        'skipped': 0
    }
    
    try:
        # Create isolated database session for this worker
        # PostgreSQL handles concurrent connections efficiently
        with get_scoped_session() as db:
            # Create isolated TradingSimulationEngine for this worker
            sim_engine = TradingSimulationEngine()
            
            # Load simulation with relationships
            sim = db.query(TradingSimulation).options(
                joinedload(TradingSimulation.prediction).joinedload(Prediction.entity)
            ).filter(TradingSimulation.simulation_id == sim_id).first()
            
            if not sim:
                logger.warning(f"⚠️ Simulation {sim_id} not found, skipping")
                stats['skipped'] = 1
                return stats
            
            prediction = sim.prediction
            entity = prediction.entity if prediction else None
            
            if not prediction:
                logger.warning(f"⚠️ Simulation {sim_id} has no prediction, skipping")
                stats['skipped'] = 1
                return stats
            
            if not entity:
                logger.warning(f"⚠️ Simulation {sim_id} has no entity, skipping")
                stats['skipped'] = 1
                return stats
            
            # Log progress (thread-safe)
            with progress_lock:
                logger.info(f"🔄 [{index}/{total}] Resimulating {entity_name} ({horizon})...")
            
            # Recalculate simulation
            updated_simulation = sim_engine.simulate_prediction(db, prediction, entity)
            
            if updated_simulation:
                # Commit happens automatically in get_scoped_session context manager
                
                decision = updated_simulation.decision
                expected_return = updated_simulation.expected_return_pct or 0
                risk_score = updated_simulation.risk_score or 0
                position_value = updated_simulation.position_value_usd or 0
                
                logger.info(
                    f"✅ [{index}/{total}] Updated {entity_name}: {decision.upper()} "
                    f"(Return: {expected_return:+.2f}%, Risk: {risk_score:.2f}, "
                    f"Position: ${position_value:.2f})"
                )
                stats['updated'] = 1
            else:
                logger.warning(f"⚠️ [{index}/{total}] {entity_name} not updated (may not meet criteria)")
                stats['skipped'] = 1
            
            stats['processed'] = 1
            
    except Exception as e:
        logger.error(f"❌ Error resimulating {sim_id}: {e}")
        import traceback
        traceback.print_exc()
        stats['errors'] = 1
        stats['processed'] = 1
    
    return stats


def resimulate_all(db: Session, limit: int = None, workers: int = 4) -> dict:
    """
    Recalculate all existing trading simulations using parallel processing.
    
    With PostgreSQL, this function can efficiently handle many concurrent database
    connections, providing significant performance improvements.
    
    Args:
        db: Database session (used only to fetch simulation list)
        limit: Optional limit on number of simulations to process
        workers: Number of parallel worker threads (default: 4 to avoid yfinance rate limits)
        
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
    logger.info(f"⚙️ Using {workers} parallel workers")
    
    if total == 0:
        return {
            'total': 0,
            'processed': 0,
            'updated': 0,
            'errors': 0,
            'skipped': 0
        }
    
    # Prepare data for parallel processing
    # Extract minimal data to avoid passing heavy ORM objects between threads
    sim_data_list = []
    for i, sim in enumerate(simulations, 1):
        prediction = sim.prediction
        entity = prediction.entity if prediction else None
        
        entity_name = entity.entity_name if entity else "Unknown"
        entity_id = entity.entity_id if entity else None
        horizon = prediction.horizon if prediction else "Unknown"
        
        sim_data_list.append((
            sim.simulation_id,
            sim.prediction_id,
            entity_id,
            entity_name,
            horizon,
            i,  # index for progress tracking
            total
        ))
    
    # Process simulations in parallel
    processed = 0
    updated = 0
    errors = 0
    skipped = 0
    
    with ThreadPoolExecutor(max_workers=workers) as executor:
        # Submit all tasks
        futures = [executor.submit(_resimulate_single, sim_data) for sim_data in sim_data_list]
        
        # Collect results as they complete
        for future in as_completed(futures):
            try:
                result = future.result()
                processed += result['processed']
                updated += result['updated']
                errors += result['errors']
                skipped += result['skipped']
            except Exception as e:
                logger.error(f"❌ Worker thread failed: {e}")
                errors += 1
    
    stats = {
        'total': total,
        'processed': processed,
        'updated': updated,
        'errors': errors,
        'skipped': skipped
    }
    
    logger.info(f"🔄 Resimulation complete: {updated} updated, {errors} errors, {skipped} skipped")
    activity_logger.log_activity(
        f"Resimulated {updated}/{total} trading simulations (parallel with {workers} workers)",
        "INFO"
    )
    
    return stats


def main():
    """Main execution function"""
    parser = argparse.ArgumentParser(
        description='Resimulate all trading simulations with parallel processing (PostgreSQL-optimized)',
        formatter_class=argparse.ArgumentDefaultsHelpFormatter
    )
    parser.add_argument(
        '--workers',
        type=int,
        default=4,
        help='Number of parallel worker threads. Reduced default to 4 to avoid yfinance rate limiting. Use 1 for sequential processing.'
    )
    parser.add_argument(
        '--limit',
        type=int,
        default=None,
        help='Limit number of simulations to process (useful for testing)'
    )
    
    args = parser.parse_args()
    
    # Validate workers
    if args.workers < 1:
        logger.error("❌ Workers must be at least 1")
        sys.exit(1)
    
    # Cap workers at reasonable limit
    max_workers = min(args.workers, os.cpu_count() * 4 or 16)
    if args.workers != max_workers:
        logger.warning(f"⚠️ Capping workers from {args.workers} to {max_workers}")
        args.workers = max_workers
    
    # PostgreSQL info for parallel processing
    if args.workers > 1:
        logger.info(f"🚀 PostgreSQL parallel processing enabled with {args.workers} workers")
        logger.info("💡 Tip: Adjust --workers based on your PostgreSQL connection pool size")
        logger.info("")
    
    logger.info("=" * 80)
    logger.info("🔄 Starting Trading Simulation Resimulation")
    logger.info("=" * 80)
    
    try:
        with Session(engine) as db:
            # Get total counts
            total_simulations = db.query(func.count(TradingSimulation.simulation_id)).scalar() or 0
            
            logger.info("📊 Current Status:")
            logger.info(f"   - Total Simulations: {total_simulations}")
            if args.limit:
                logger.info(f"   - Limit: {args.limit}")
            logger.info(f"   - Workers: {args.workers}")
            logger.info("")
            
            # Resimulate all
            logger.info("=" * 80)
            logger.info("STEP 1: Resimulate All Trading Simulations")
            logger.info("=" * 80)
            
            start_time = datetime.now()
            stats = resimulate_all(db, limit=args.limit, workers=args.workers)
            duration = (datetime.now() - start_time).total_seconds()
            
            logger.info("")
            
            # Final summary
            logger.info("=" * 80)
            logger.info("✅ RESIMULATION COMPLETE")
            logger.info("=" * 80)
            logger.info(f"⏱️ Duration: {duration:.1f}s ({duration/60:.1f} minutes)")
            logger.info(f"🔄 Simulations: {stats['updated']}/{stats['total']} updated")
            logger.info(f"   - Processed: {stats['processed']}")
            logger.info(f"   - Updated: {stats['updated']}")
            logger.info(f"   - Errors: {stats['errors']}")
            logger.info(f"   - Skipped: {stats['skipped']}")
            if stats['processed'] > 0 and duration > 0:
                rate = stats['processed'] / duration
                logger.info(f"   - Rate: {rate:.1f} simulations/second")
            logger.info("")
            
            logger.info("=" * 80)
            
    except Exception as e:
        logger.error(f"❌ Fatal error during resimulation: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()
