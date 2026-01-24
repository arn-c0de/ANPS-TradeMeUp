"""
Check if EntityMappingAgent is creating NewsEntityMapping entries
"""

import logging
from sqlalchemy import create_engine, func
from sqlalchemy.orm import Session
from src.config.settings import settings
from src.models.entities import NewsEntityMapping, Entity
from src.models.processed_news import ProcessedNews
from src.models.raw_news import RawNews

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

engine = create_engine(settings.database_url)

def check_entity_mappings():
    """Check entity mapping status"""
    
    with Session(engine) as db:
        total_processed = db.query(func.count(ProcessedNews.news_id)).scalar()
        total_mappings = db.query(func.count(NewsEntityMapping.mapping_id)).scalar()
        
        # Count processed news WITH mappings
        with_mappings = db.query(func.count(func.distinct(NewsEntityMapping.news_id))).scalar()
        
        # Processed news WITHOUT mappings
        without_mappings = total_processed - with_mappings
        
        logger.info("="*70)
        logger.info("🏢 ENTITY MAPPING STATUS")
        logger.info("="*70)
        logger.info(f"Total Processed News: {total_processed}")
        logger.info(f"Processed News WITH entity mappings: {with_mappings}")
        logger.info(f"Processed News WITHOUT mappings: {without_mappings}")
        logger.info(f"Total Entity Mappings: {total_mappings}")
        logger.info("")
        
        # Show sample mappings
        if total_mappings > 0:
            logger.info("Sample Entity Mappings:")
            samples = db.query(NewsEntityMapping).limit(10).all()
            for m in samples:
                entity = db.query(Entity).filter(Entity.entity_id == m.entity_id).first()
                logger.info(f"  News: {m.news_id[:8]}, Entity: {m.entity_id} ({entity.entity_name if entity else 'Unknown'}), Confidence: {m.confidence}")
        
        logger.info("\n" + "="*70)
        logger.info("🔍 DIAGNOSIS")
        logger.info("="*70)
        logger.info(f"✅ Processed News exist: {total_processed}")
        logger.info(f"{'✅' if with_mappings > 0 else '❌'} Entity Mappings: {with_mappings}/{total_processed} ({(with_mappings/total_processed*100):.1f}%)")
        
        if without_mappings > 1000:
            logger.warning(f"\n⚠️ {without_mappings} processed news have NO entity mappings!")
            logger.warning("This blocks ImpactScore creation!")
            logger.warning("")
            logger.warning("💡 SOLUTION: Run EntityMappingAgent on backlog")
            logger.warning("   Command: python scripts/run_full_pipeline.py --phase entity")

if __name__ == "__main__":
    check_entity_mappings()
