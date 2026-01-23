"""
RSS Feed Fetcher - Fetch news without AI analysis
Runs continuously with configurable interval
"""
import sys
import logging
import time
import signal
from pathlib import Path
from datetime import datetime

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from src.agents.ingestion_agent import IngestionAgent
from src.models.database import SessionLocal
from src.utils.activity_logger import activity_logger

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Global flag for graceful shutdown
running = True


def signal_handler(signum, frame):
    """Handle shutdown signals"""
    global running
    logger.info("\n⚠️ Shutdown signal received, stopping after current fetch...")
    running = False


def fetch_once():
    """Execute single RSS fetch"""
    db = SessionLocal()
    try:
        # Create ingestion agent and fetch
        agent = IngestionAgent(db)
        
        logger.info("Fetching RSS feeds...")
        results = agent.fetch_all_rss_feeds()
        
        # Calculate totals
        total_new = sum(results.values())
        total_sources = len(results)
        
        # Log results
        logger.info("=" * 60)
        logger.info(f"RSS FETCH COMPLETE at {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        logger.info(f"New Articles: {total_new}")
        logger.info(f"Sources Checked: {total_sources}")
        logger.info("=" * 60)
        
        # Detailed results
        for source, count in results.items():
            logger.info(f"  {source}: {count} new articles")
        
        activity_logger.log_activity(
            f"RSS Fetch: {total_new} new articles from {total_sources} sources",
            "SUCCESS" if total_new > 0 else "INFO"
        )
        
        return total_new, total_sources
        
    except Exception as e:
        logger.error(f"❌ Error during RSS fetch: {e}", exc_info=True)
        activity_logger.log_activity(f"RSS Fetch Error: {str(e)}", "ERROR")
        return 0, 0
    finally:
        db.close()


def main():
    """Fetch RSS feeds continuously"""
    global running
    
    # Setup signal handlers
    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)
    
    logger.info("=" * 60)
    logger.info("RSS FEED FETCHER - Continuous News Collection")
    logger.info("=" * 60)
    logger.info("Press Ctrl+C to stop gracefully")
    logger.info("")
    
    # Configuration
    fetch_interval = 300  # 5 minutes
    iteration = 0
    total_articles = 0
    
    while running:
        iteration += 1
        
        try:
            logger.info(f"\n{'='*60}")
            logger.info(f"FETCH ITERATION #{iteration}")
            logger.info(f"{'='*60}")
            
            # Execute fetch
            new_articles, sources_checked = fetch_once()
            total_articles += new_articles
            
            logger.info(f"\n✅ Fetch iteration #{iteration} completed!")
            logger.info(f"📊 Session Total: {total_articles} articles collected")
            
            if running:
                logger.info(f"\n⏰ Next fetch in {fetch_interval} seconds ({fetch_interval//60} minutes)...")
                logger.info(f"   (Press Ctrl+C to stop)")
                
                # Sleep with periodic checks for shutdown signal
                for i in range(fetch_interval):
                    if not running:
                        break
                    time.sleep(1)
                    
        except KeyboardInterrupt:
            logger.info("\n⚠️ Keyboard interrupt detected")
            running = False
            break
        except Exception as e:
            logger.error(f"❌ Error in main loop: {e}", exc_info=True)
            if running:
                logger.info(f"⏰ Retrying in {fetch_interval} seconds...")
                time.sleep(fetch_interval)
    
    logger.info("\n" + "=" * 60)
    logger.info("RSS FETCHER STOPPED")
    logger.info(f"Total Articles Collected: {total_articles}")
    logger.info(f"Total Iterations: {iteration}")
    logger.info("=" * 60)
    
    return 0


if __name__ == "__main__":
    try:
        exit_code = main()
    except KeyboardInterrupt:
        logger.info("\n⚠️ RSS fetch interrupted by user")
        exit_code = 130
    except Exception as e:
        logger.error(f"❌ Fatal error: {e}", exc_info=True)
        exit_code = 1
    
    logger.info("\nPress ENTER to close this window...")
    input()
    sys.exit(exit_code)
