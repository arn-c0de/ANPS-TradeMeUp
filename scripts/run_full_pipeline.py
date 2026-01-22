"""Script to run the full MVP pipeline: Agents 1, 1.5, 2, 3."""
import sys
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from src.models.database import SessionLocal
from src.agents.ingestion_agent import IngestionAgent
from src.agents.data_quality_agent import DataQualityAgent
from src.agents.content_understanding_agent import ContentUnderstandingAgent
from src.agents.entity_mapping_agent import EntityMappingAgent
from src.config.settings import settings
import logging

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


def main():
    """Run the complete MVP pipeline."""
    logger.info("=" * 60)
    logger.info("TradeMeUp MVP Pipeline - Phase 1")
    logger.info("=" * 60)

    # Create database session
    db = SessionLocal()

    try:
        # ===== AGENT 1: Data Ingestion =====
        logger.info("\n[1/4] Running Agent 1: Data Ingestion...")
        ingestion = IngestionAgent(db)

        # Fetch from RSS feeds
        rss_results = ingestion.fetch_all_rss_feeds()
        logger.info(f"RSS results: {rss_results}")

        # Fetch from News API (if key available)
        if settings.news_api_key:
            api_count = ingestion.fetch_news_api(settings.news_api_key)
            logger.info(f"News API: {api_count} new articles")

        ing_stats = ingestion.get_statistics()
        logger.info(f"Ingestion stats: {ing_stats}")

        # ===== AGENT 1.5: Data Quality =====
        logger.info("\n[2/4] Running Agent 1.5: Data Quality...")
        quality = DataQualityAgent(db)

        quality_results = quality.process_batch(limit=100)
        logger.info(f"Quality results: {quality_results}")

        qual_stats = quality.get_statistics()
        logger.info(f"Quality stats: {qual_stats}")

        # ===== AGENT 2: Content Understanding =====
        logger.info("\n[3/4] Running Agent 2: Content Understanding (NLP)...")
        logger.info(f"Using LLM provider: {settings.llm_provider}")

        content = ContentUnderstandingAgent(db)

        # Process smaller batch (LLM is slower)
        content_results = content.process_batch(limit=5)
        logger.info(f"Content understanding results: {content_results}")

        cont_stats = content.get_statistics()
        logger.info(f"Content stats: {cont_stats}")

        # ===== AGENT 3: Entity Mapping =====
        logger.info("\n[4/4] Running Agent 3: Entity Mapping...")
        entities = EntityMappingAgent(db)

        entity_results = entities.process_batch(limit=5)
        logger.info(f"Entity mapping results: {entity_results}")

        ent_stats = entities.get_statistics()
        logger.info(f"Entity stats: {ent_stats}")

        # ===== SUMMARY =====
        logger.info("\n" + "=" * 60)
        logger.info("PIPELINE COMPLETE - SUMMARY")
        logger.info("=" * 60)
        logger.info(f"Total articles in database: {ing_stats['total_articles']}")
        logger.info(f"Articles assessed for quality: {qual_stats['total_assessed']}")
        logger.info(f"High quality articles: {qual_stats['high_quality']}")
        logger.info(f"Articles processed by NLP: {cont_stats['total_processed']}")
        logger.info(f"Entities mapped: {ent_stats['total_entities']}")
        logger.info(f"Top entities: {ent_stats['top_entities'][:5]}")
        logger.info("=" * 60)

    except Exception as e:
        logger.error(f"Error in pipeline: {e}", exc_info=True)
        raise
    finally:
        db.close()


if __name__ == "__main__":
    main()
