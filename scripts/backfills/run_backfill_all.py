"""Master backfill script."""

from datetime import datetime
import logging
from pathlib import Path
import sys

PROJECT_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(PROJECT_ROOT))

from src.agents.entity_mapping_agent import EntityMappingAgent
from src.agents.impact_scoring_agent import ImpactScoringAgent
from src.agents.surprise_quantification_agent import SurpriseQuantificationAgent
from src.agents.prediction_agent import PredictionAgent
from src.utils.activity_logger import activity_logger

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


def backfill_phase(agent, phase_name: str, batch_size: int = 100):
    """Run backfill for a single phase"""
    logger.info("\n" + "="*70)
    logger.info(f"📦 PHASE: {phase_name.upper()}")
    logger.info("="*70)
    
    total_processed = 0
    total_items = 0  # Total items found
    batch_num = 1
    start_time = datetime.now()
    
    while True:
        batch_start = datetime.now()
        logger.info(f"\n🔄 Batch #{batch_num} (size: {batch_size}) - Total processed so far: {total_processed}")
        
        try:
            result = agent.process_batch(limit=batch_size)
            
            processed = result.get('processed', 0)
            total_processed += processed
            
            # Calculate items per second
            batch_duration = (datetime.now() - batch_start).total_seconds()
            items_per_sec = processed / batch_duration if batch_duration > 0 else 0
            
            logger.info(f"✅ Batch #{batch_num} done in {batch_duration:.1f}s ({items_per_sec:.1f} items/s)")
            logger.info(f"   Result: {result}")
            logger.info(f"   📊 CUMULATIVE: {total_processed} items processed")
            
            # Log progress to activity logger
            activity_logger.log_activity(
                f"{phase_name}: Batch #{batch_num} complete - {total_processed} total",
                "INFO"
            )
            
            if processed == 0:
                logger.info(f"\n✅ {phase_name} complete! No more items to process.")
                break
            
            # Safety: max 100 batches to prevent infinite loops
            if batch_num >= 100:
                logger.warning("⚠️ Reached max batches (100), stopping to prevent runaway")
                break
            
            batch_num += 1
            
        except Exception as e:
            logger.error(f"❌ Error in batch #{batch_num}: {e}", exc_info=True)
            activity_logger.log_activity(f"{phase_name} batch #{batch_num} failed: {str(e)}", "ERROR")
            break
    
    duration = (datetime.now() - start_time).total_seconds()
    avg_speed = total_processed / duration if duration > 0 else 0
    logger.info(f"⏱️  {phase_name} took {duration:.1f}s, processed {total_processed} items ({avg_speed:.2f} items/s)")
    
    return total_processed


def run_full_backfill(batch_size: int = 100):
    """Run complete backfill pipeline"""
    start_time = datetime.now()
    
    logger.info("="*70)
    logger.info("🚀 STARTING FULL BACKFILL PIPELINE")
    logger.info("="*70)
    logger.info(f"Batch size: {batch_size}")
    logger.info(f"Start time: {start_time}")
    
    stats = {}
    
    # Phase 1: Entity Mappings
    logger.info("\n" + "#"*70)
    logger.info("# PHASE 1/4: Entity Mappings")
    logger.info("#"*70)
    entity_agent = EntityMappingAgent()
    stats['entity_mappings'] = backfill_phase(entity_agent, "Entity Mapping", batch_size)
    
    # Phase 2: Impact Scores
    logger.info("\n" + "#"*70)
    logger.info("# PHASE 2/4: Impact Scores")
    logger.info("#"*70)
    impact_agent = ImpactScoringAgent()
    stats['impact_scores'] = backfill_phase(impact_agent, "Impact Scoring", batch_size)
    
    # Phase 3: Surprise Scores (only for earnings/guidance)
    logger.info("\n" + "#"*70)
    logger.info("# PHASE 3/4: Surprise Scores")
    logger.info("#"*70)
    surprise_agent = SurpriseQuantificationAgent()
    stats['surprise_scores'] = backfill_phase(surprise_agent, "Surprise Quantification", batch_size)
    
    # Phase 4: Predictions
    logger.info("\n" + "#"*70)
    logger.info("# PHASE 4/4: Predictions")
    logger.info("#"*70)
    prediction_agent = PredictionAgent()
    stats['predictions'] = backfill_phase(prediction_agent, "Prediction Generation", batch_size)
    
    # Final summary
    duration = (datetime.now() - start_time).total_seconds()
    
    logger.info("\n" + "="*70)
    logger.info("🎉 BACKFILL PIPELINE COMPLETE!")
    logger.info("="*70)
    logger.info(f"Total duration: {duration:.1f}s ({duration/60:.1f} minutes)")
    logger.info("\n📊 PROCESSING SUMMARY:")
    logger.info(f"  Entity Mappings: {stats.get('entity_mappings', 0)} articles")
    logger.info(f"  Impact Scores: {stats.get('impact_scores', 0)} articles")
    logger.info(f"  Surprise Scores: {stats.get('surprise_scores', 0)} articles")
    logger.info(f"  Predictions: {stats.get('predictions', 0)} articles")
    logger.info("="*70)
    
    activity_logger.log_activity(f"Full backfill complete: {stats}", "SUCCESS")
    
    return stats


if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(description='Run full backfill pipeline')
    parser.add_argument('--batch-size', type=int, default=100, help='Batch size (default: 100)')
    args = parser.parse_args()
    
    stats = run_full_backfill(batch_size=args.batch_size)
    
    logger.info("\n✅ All done! Check the dashboard to see updated statistics.")
