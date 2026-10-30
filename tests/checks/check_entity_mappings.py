"""
Check if EntityMappingAgent is creating NewsEntityMapping entries
"""

import logging

from sqlalchemy import create_engine, func, select
from sqlalchemy.orm import Session

from src.config.settings import settings
from src.models.entities import Entity, NewsEntityMapping
from src.models.processed_news import ProcessedNews

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

engine = create_engine(settings.database_url)

def check_entity_mappings():
    """Check entity mapping status"""

    with Session(engine) as db:
        total_processed = db.scalar(select(func.count(ProcessedNews.news_id)))
        total_mappings = db.scalar(select(func.count(NewsEntityMapping.mapping_id)))

        # Count processed news WITH mappings
        with_mappings = db.scalar(select(func.count(func.distinct(NewsEntityMapping.news_id))))

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
            samples = db.scalars(select(NewsEntityMapping).limit(10)).all()
            for m in samples:
                entity = db.scalar(select(Entity).where(Entity.entity_id == m.entity_id).limit(1))
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
