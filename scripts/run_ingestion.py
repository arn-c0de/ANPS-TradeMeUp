"""Script to manually run the ingestion agent."""
import sys
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

import logging

from src.agents.ingestion_agent import IngestionAgent
from src.config.settings import settings
from src.models.database import SessionLocal

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


def main():
    """Run the ingestion agent."""
    logger.info("Starting ingestion agent...")

    try:
        with SessionLocal() as db:
            agent = IngestionAgent(db)

            # Fetch from RSS feeds
            logger.info("Fetching from RSS feeds...")
            rss_results = agent.fetch_all_rss_feeds()
            logger.info(f"RSS results: {rss_results}")

            # Fetch from News API (if key is available)
            if settings.news_api_key:
                logger.info("Fetching from News API...")
                api_count = agent.fetch_news_api(settings.news_api_key)
                logger.info(f"News API: {api_count} new articles")

            # Print statistics
            stats = agent.get_statistics()
            logger.info("=== Ingestion Statistics ===")
            logger.info(f"Total articles in database: {stats['total_articles']}")
            logger.info(f"Articles by source: {stats['by_source']}")
            logger.info(f"Articles in last 24h: {stats['last_24_hours']}")

    except Exception as e:
        logger.error(f"Error running ingestion agent: {e}")
        raise

    logger.info("Ingestion complete!")


if __name__ == "__main__":
    main()
