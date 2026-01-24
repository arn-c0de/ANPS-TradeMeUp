"""
Backfill Entity Mappings for processed news
Runs EntityMappingAgent on all processed news without entity mappings
"""

import logging
import sys
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

from src.agents.entity_mapping_agent import EntityMappingAgent
from src.utils.activity_logger import activity_logger

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


def backfill_entity_mappings(batch_size: int = 100):
    """
    Backfill entity mappings for all processed news without mappings
    
    Args:
        batch_size: Number of articles to process per batch
    """
    logger.info("="*70)
    logger.info("🏢 BACKFILLING ENTITY MAPPINGS")
    logger.info("="*70)
    
    agent = EntityMappingAgent()
    total_processed = 0
    batch_num = 1
    
    while True:
        logger.info(f"\n📦 Processing batch #{batch_num} (size: {batch_size})")
        
        try:
            result = agent.process_batch(limit=batch_size)
            
            processed = result.get('processed', 0)
            total_processed += processed
            
            logger.info(f"Batch #{batch_num} result: {result}")
            activity_logger.log_activity(f"Entity mapping batch #{batch_num}: {processed} articles", "SUCCESS")
            
            # If no articles were processed, we're done
            if processed == 0:
                logger.info("\n✅ Backfill complete! No more articles to process.")
                break
            
            batch_num += 1
            
        except Exception as e:
            logger.error(f"Error in batch #{batch_num}: {e}", exc_info=True)
            activity_logger.log_activity(f"Entity mapping batch #{batch_num} failed: {str(e)}", "ERROR")
            break
    
    logger.info("\n" + "="*70)
    logger.info(f"📊 BACKFILL SUMMARY")
    logger.info("="*70)
    logger.info(f"Total batches processed: {batch_num}")
    logger.info(f"Total articles processed: {total_processed}")
    
    return total_processed


if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(description='Backfill entity mappings')
    parser.add_argument('--batch-size', type=int, default=100, help='Batch size (default: 100)')
    args = parser.parse_args()
    
    total = backfill_entity_mappings(batch_size=args.batch_size)
    
    logger.info(f"\n✅ Done! Processed {total} articles total.")
    logger.info("Now run backfill for Impact Scores and Surprise Scores...")
