"""
Backfill Entity Mappings with Theme-Based ETF Support
Run this to map macro/sector news to tradeable ETFs
"""

import logging
import sys
from pathlib import Path
from datetime import datetime

# Get project root (two levels up from tests/backfills/)
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))

from src.agents.entity_mapping_agent import EntityMappingAgent

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


def backfill_entity_mappings(batch_size: int = 50, max_batches: int = 50):
    """Backfill entity mappings with theme support"""
    
    start_time = datetime.now()
    
    logger.info("="*70)
    logger.info("🏢 ENTITY MAPPING BACKFILL (with Theme-Based ETFs)")
    logger.info("="*70)
    
    agent = EntityMappingAgent()
    total_processed = 0
    total_mappings = 0
    batch_num = 1
    current_offset = 0
    
    while batch_num <= max_batches:
        logger.info(f"\n🔄 Batch #{batch_num} (offset: {current_offset})")
        
        result = agent.process_batch(limit=batch_size, offset=current_offset)
        processed = result.get('processed', 0)
        mappings = result.get('total_mappings', 0)
        
        total_processed += processed
        total_mappings += mappings
        
        logger.info(f"  ✅ Processed: {processed}, Mappings: {mappings}")
        logger.info(f"  📊 Cumulative: {total_processed} articles, {total_mappings} mappings")
        
        if processed == 0:
            logger.info("  🏁 No more articles to process")
            break
        
        # Increment offset by batch_size to skip processed articles in next batch
        current_offset += batch_size
        batch_num += 1
    
    duration = (datetime.now() - start_time).total_seconds()
    
    logger.info("\n" + "="*70)
    logger.info("🎉 ENTITY MAPPING COMPLETE!")
    logger.info("="*70)
    logger.info(f"Duration: {duration:.1f}s ({duration/60:.1f} minutes)")
    logger.info(f"Articles Processed: {total_processed}")
    logger.info(f"Entity Mappings Created: {total_mappings}")
    logger.info(f"Avg Mappings/Article: {total_mappings/max(1, total_processed):.1f}")
    logger.info("="*70)
    
    return {'processed': total_processed, 'mappings': total_mappings}


if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(description='Backfill entity mappings')
    parser.add_argument('--batch-size', type=int, default=50, help='Batch size')
    parser.add_argument('--max-batches', type=int, default=50, help='Maximum batches')
    args = parser.parse_args()
    
    stats = backfill_entity_mappings(
        batch_size=args.batch_size,
        max_batches=args.max_batches
    )
    
    logger.info(f"\n✅ Done! Run quick_backfill_predictions.py next to generate predictions!")
