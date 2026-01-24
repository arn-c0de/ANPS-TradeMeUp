"""
Backfill Impact Scores and Surprise Scores
Runs after entity mappings are complete
"""

import logging
import sys
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

from src.agents.impact_scoring_agent import ImpactScoringAgent
from src.agents.surprise_quantification_agent import SurpriseQuantificationAgent
from src.utils.activity_logger import activity_logger

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


def backfill_impact_scores(batch_size: int = 100):
    """Backfill impact scores"""
    logger.info("\n" + "="*70)
    logger.info("📊 BACKFILLING IMPACT SCORES")
    logger.info("="*70)
    
    agent = ImpactScoringAgent()
    total_processed = 0
    batch_num = 1
    
    while True:
        logger.info(f"\n📦 Processing batch #{batch_num} (size: {batch_size})")
        
        try:
            result = agent.process_batch(limit=batch_size)
            
            processed = result.get('processed', 0)
            total_processed += processed
            
            logger.info(f"Batch #{batch_num} result: {result}")
            
            if processed == 0:
                logger.info("\n✅ Impact scoring backfill complete!")
                break
            
            batch_num += 1
            
        except Exception as e:
            logger.error(f"Error in batch #{batch_num}: {e}", exc_info=True)
            break
    
    return total_processed


def backfill_surprise_scores(batch_size: int = 100):
    """Backfill surprise scores (for earnings/guidance only)"""
    logger.info("\n" + "="*70)
    logger.info("🎯 BACKFILLING SURPRISE SCORES")
    logger.info("="*70)
    
    agent = SurpriseQuantificationAgent()
    total_processed = 0
    batch_num = 1
    
    while True:
        logger.info(f"\n📦 Processing batch #{batch_num} (size: {batch_size})")
        
        try:
            result = agent.process_batch(limit=batch_size)
            
            processed = result.get('processed', 0)
            total_processed += processed
            
            logger.info(f"Batch #{batch_num} result: {result}")
            
            if processed == 0:
                logger.info("\n✅ Surprise scoring backfill complete!")
                break
            
            batch_num += 1
            
        except Exception as e:
            logger.error(f"Error in batch #{batch_num}: {e}", exc_info=True)
            break
    
    return total_processed


if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(description='Backfill impact and surprise scores')
    parser.add_argument('--batch-size', type=int, default=100, help='Batch size (default: 100)')
    parser.add_argument('--skip-impact', action='store_true', help='Skip impact score backfill')
    parser.add_argument('--skip-surprise', action='store_true', help='Skip surprise score backfill')
    args = parser.parse_args()
    
    total_impact = 0
    total_surprise = 0
    
    if not args.skip_impact:
        total_impact = backfill_impact_scores(batch_size=args.batch_size)
    
    if not args.skip_surprise:
        total_surprise = backfill_surprise_scores(batch_size=args.batch_size)
    
    logger.info("\n" + "="*70)
    logger.info("📊 BACKFILL SUMMARY")
    logger.info("="*70)
    logger.info(f"Impact scores processed: {total_impact}")
    logger.info(f"Surprise scores processed: {total_surprise}")
    logger.info("\n✅ Done! Now run PredictionAgent to generate predictions...")
