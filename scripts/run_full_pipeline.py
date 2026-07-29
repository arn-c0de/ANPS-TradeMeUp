"""Script to run the full MVP pipeline: Agents 1, 1.5, 2, 3."""
import sys
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

import logging

from src.agents import build_agent
from src.agents.content_understanding_agent import ContentUnderstandingAgent
from src.agents.data_quality_agent import DataQualityAgent
from src.agents.entity_mapping_agent import EntityMappingAgent
from src.agents.ingestion_agent import IngestionAgent
from src.config.settings import settings
from src.models.database import SessionLocal

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# The LLM makes content understanding much slower than the other stages, so it
# and the entity mapping that follows it run in small batches.
QUALITY_BATCH = 100
LLM_BATCH = 5


def _run_stage(step: str, label: str, agent, limit: int) -> dict:
    """Run one batch stage and log both its result and the agent's totals."""
    logger.info(f"\n[{step}] Running {label}...")

    results = agent.process_batch(limit=limit)
    logger.info(f"{label} results: {results}")

    stats = agent.get_statistics()
    logger.info(f"{label} stats: {stats}")
    return stats


def main():
    """Run the complete MVP pipeline."""
    logger.info("=" * 60)
    logger.info("TradeMeUp MVP Pipeline - Phase 1")
    logger.info("=" * 60)

    try:
        with SessionLocal() as db:
            # ===== AGENT 1: Data Ingestion =====
            # Fetching is not a process_batch stage, so it stays explicit.
            logger.info("\n[1/4] Running Agent 1: Data Ingestion...")
            ingestion = build_agent(IngestionAgent, db)

            rss_results = ingestion.fetch_all_rss_feeds()
            logger.info(f"RSS results: {rss_results}")

            if settings.news_api_key:
                api_count = ingestion.fetch_news_api(settings.news_api_key)
                logger.info(f"News API: {api_count} new articles")

            ing_stats = ingestion.get_statistics()
            logger.info(f"Ingestion stats: {ing_stats}")

            # ===== AGENTS 1.5, 2, 3 =====
            # build_agent passes the session only to agents that still take
            # one; these three open their own and reject a positional argument.
            qual_stats = _run_stage(
                "2/4", "Agent 1.5: Data Quality",
                build_agent(DataQualityAgent, db), QUALITY_BATCH,
            )

            logger.info(f"Using LLM provider: {settings.llm_provider}")
            cont_stats = _run_stage(
                "3/4", "Agent 2: Content Understanding (NLP)",
                build_agent(ContentUnderstandingAgent, db), LLM_BATCH,
            )

            ent_stats = _run_stage(
                "4/4", "Agent 3: Entity Mapping",
                build_agent(EntityMappingAgent, db), LLM_BATCH,
            )

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


if __name__ == "__main__":
    main()
