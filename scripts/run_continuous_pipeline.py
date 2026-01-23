"""
Continuous Pipeline Runner
Runs the pipeline continuously in the background, checking for new articles periodically
"""
import sys
import time
import logging
from pathlib import Path
from datetime import datetime

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from src.models.database import SessionLocal
from src.agents.ingestion_agent import IngestionAgent
from src.agents.data_quality_agent import DataQualityAgent
from src.agents.content_understanding_agent import ContentUnderstandingAgent
from src.agents.entity_mapping_agent import EntityMappingAgent
from src.agents.surprise_quantification_agent import SurpriseQuantificationAgent
from src.agents.regime_detection_agent import RegimeDetectionAgent
from src.agents.impact_scoring_agent import ImpactScoringAgent
from src.agents.prediction_agent import PredictionAgent
from src.config.settings import settings
from src.utils.activity_logger import activity_logger

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


class ContinuousPipeline:
    """Continuously running pipeline for production mode"""
    
    def __init__(self, check_interval: int = 300):
        """
        Initialize continuous pipeline
        
        Args:
            check_interval: Seconds between pipeline runs (default: 300 = 5 minutes)
        """
        self.check_interval = check_interval
        self.running = False
        self.db = None
        
    def run(self):
        """Run the pipeline continuously"""
        self.running = True
        activity_logger.log_activity("Continuous Pipeline Mode STARTED", "SUCCESS")
        logger.info(f"Starting continuous pipeline (check every {self.check_interval}s)")
        
        iteration = 0
        
        while self.running:
            try:
                iteration += 1
                start_time = datetime.now()
                
                logger.info(f"=" * 60)
                logger.info(f"Pipeline Iteration #{iteration} - {start_time}")
                logger.info(f"=" * 60)
                
                activity_logger.log_activity(f"Starting Pipeline Iteration #{iteration}", "INFO")
                
                # Create fresh database session
                self.db = SessionLocal()
                
                # Run all pipeline phases
                new_articles = self._run_pipeline_iteration()
                
                # Close database session
                self.db.close()
                
                duration = (datetime.now() - start_time).total_seconds()
                logger.info(f"Iteration #{iteration} completed in {duration:.1f}s")
                activity_logger.log_activity(f"Iteration #{iteration} completed in {duration:.1f}s", "SUCCESS")
                
                # Only wait if there were new articles or it's the first iteration
                # Otherwise continue processing existing backlog immediately
                if iteration == 1 or new_articles > 0:
                    logger.info(f"Waiting {self.check_interval}s until next check...")
                    time.sleep(self.check_interval)
                else:
                    logger.info("No new articles, checking again in 10 seconds...")
                    time.sleep(10)
                
            except KeyboardInterrupt:
                logger.info("Stopping continuous pipeline (keyboard interrupt)")
                self.running = False
                break
            except Exception as e:
                logger.error(f"Error in pipeline iteration: {e}")
                activity_logger.log_activity(f"Pipeline error: {str(e)}", "ERROR")
                # Wait before retry
                time.sleep(60)
    
    def _run_pipeline_iteration(self):
        """Run one complete pipeline iteration
        
        Returns:
            Number of new articles ingested
        """
        try:
            # Phase 1: Data Ingestion
            activity_logger.log_phase(1, "Data Ingestion")
            ingestion = IngestionAgent(self.db)
            rss_results = ingestion.fetch_all_rss_feeds()
            new_articles = sum(rss_results.values())
            logger.info(f"Ingested: {rss_results}")
            
            # Phase 2: Quality Check (process unassessed articles)
            activity_logger.log_phase(2, "Quality Assessment")
            quality = DataQualityAgent(self.db)
            quality_results = quality.process_batch(limit=50)
            logger.info(f"Quality check: {quality_results}")
            
            # Phase 3: Content Understanding (process unanalyzed high-quality articles)
            activity_logger.log_phase(3, "Content Analysis")
            content = ContentUnderstandingAgent(self.db)
            content_results = content.process_batch(limit=10)
            logger.info(f"NLP Analysis: {content_results}")
            
            # Phase 4: Entity Mapping
            activity_logger.log_phase(4, "Entity Mapping")
            entities = EntityMappingAgent(self.db)
            entity_results = entities.process_batch(limit=10)
            logger.info(f"Entities: {entity_results}")
            
            # Phase 5: Market Regime
            activity_logger.log_phase(5, "Market Regime")
            regime = RegimeDetectionAgent(self.db)
            regime_result = regime.update_regime()
            logger.info(f"Regime: {regime_result}")
            
            # Phase 6: Surprise Quantification
            activity_logger.log_phase(6, "Surprise Quantification")
            surprise = SurpriseQuantificationAgent(self.db)
            surprise_results = surprise.process_batch(limit=20)
            logger.info(f"Surprises: {surprise_results}")
            
            # Phase 7: Impact Scoring
            activity_logger.log_phase(7, "Impact Scoring")
            impact = ImpactScoringAgent(self.db)
            impact_results = impact.process_batch(limit=20)
            logger.info(f"Impact: {impact_results}")
            
            # Phase 8: Predictions
            activity_logger.log_phase(8, "Predictions")
            predictions = PredictionAgent(self.db)
            pred_results = predictions.process_batch(limit=50)
            logger.info(f"Predictions: {pred_results}")
            
            return new_articles
            
        except Exception as e:
            logger.error(f"Error in pipeline iteration: {e}", exc_info=True)
            raise
    
    def stop(self):
        """Stop the continuous pipeline"""
        logger.info("Stopping continuous pipeline...")
        activity_logger.log_activity("Continuous Pipeline STOPPED", "INFO")
        self.running = False


def main():
    """Main entry point"""
    import argparse
    
    parser = argparse.ArgumentParser(description='Run TradeMeUp pipeline continuously')
    parser.add_argument(
        '--interval',
        type=int,
        default=300,
        help='Seconds between pipeline runs (default: 300)'
    )
    
    args = parser.parse_args()
    
    pipeline = ContinuousPipeline(check_interval=args.interval)
    
    try:
        pipeline.run()
    except KeyboardInterrupt:
        pipeline.stop()
        logger.info("Pipeline stopped by user")


if __name__ == "__main__":
    main()
