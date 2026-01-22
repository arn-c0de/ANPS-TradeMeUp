"""
Complete MVP Pipeline Script - All Agents

Runs the full TradeMeUp pipeline:
1. Agent 1: Data Ingestion
2. Agent 1.5: Data Quality
3. Agent 2: Content Understanding
4. Agent 3: Entity Mapping
5. Agent 4.5: Surprise Quantification
6. Agent 5: Market Regime Detection
7. Agent 4: Impact Scoring
8. Agent 6: Prediction Generation
"""
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
from src.agents.surprise_quantification_agent import SurpriseQuantificationAgent
from src.agents.regime_detection_agent import RegimeDetectionAgent
from src.agents.impact_scoring_agent import ImpactScoringAgent
from src.agents.prediction_agent import PredictionAgent
from src.config.settings import settings
from src.utils.activity_logger import activity_logger
import logging
from datetime import datetime

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


def print_section(title: str):
    """Print formatted section header."""
    logger.info("\n" + "=" * 70)
    logger.info(f"  {title}")
    logger.info("=" * 70)


def main():
    """Run the complete MVP pipeline."""
    start_time = datetime.now()

    activity_logger.log_pipeline_start("TradeMeUp MVP Pipeline")
    
    print_section("TradeMeUp MVP Pipeline - Complete Run")
    logger.info(f"Start Time: {start_time}")
    logger.info(f"LLM Provider: {settings.llm_provider}")
    logger.info(f"Database: {settings.database_url}")

    # Create database session
    db = SessionLocal()

    try:
        # ===== PHASE 1: DATA COLLECTION =====
        activity_logger.log_phase(1, "Data Collection (Agent 1)")
        print_section("PHASE 1: Data Collection (Agent 1)")

        activity_logger.log_agent_start("Ingestion Agent", "1")
        ingestion = IngestionAgent(db)

        # Fetch from RSS feeds
        logger.info("Fetching from RSS feeds...")
        activity_logger.log_activity("Fetching articles from RSS feeds...", "PROCESSING")
        rss_results = ingestion.fetch_all_rss_feeds()
        logger.info(f"RSS Results: {rss_results}")
        activity_logger.log_activity(f"Fetched {rss_results.get('new_articles', 0)} new articles", "SUCCESS")

        # Fetch from News API (if available)
        if settings.news_api_key:
            logger.info("Fetching from News API...")
            api_count = ingestion.fetch_news_api(settings.news_api_key)
            logger.info(f"News API: {api_count} new articles")
            activity_logger.log_activity(f"News API: {api_count} new articles", "SUCCESS")

        ing_stats = ingestion.get_statistics()
        logger.info(f"📊 Total articles in DB: {ing_stats['total_articles']}")
        activity_logger.log_agent_success("Ingestion Agent", ing_stats['total_articles'])

        # ===== PHASE 2: QUALITY ASSESSMENT =====
        activity_logger.log_phase(2, "Quality Assessment (Agent 1.5)")
        print_section("PHASE 2: Quality Assessment (Agent 1.5)")

        activity_logger.log_agent_start("Data Quality Agent", "2")
        quality = DataQualityAgent(db)
        quality_results = quality.process_batch(limit=50)
        logger.info(f"Quality Results: {quality_results}")

        qual_stats = quality.get_statistics()
        logger.info(f"📊 Quality Stats: {qual_stats}")
        activity_logger.log_agent_success("Data Quality Agent", quality_results.get('processed', 0))

        # ===== PHASE 3: CONTENT UNDERSTANDING =====
        activity_logger.log_phase(3, "Content Understanding (Agent 2 - NLP)")
        print_section("PHASE 3: Content Understanding (Agent 2 - NLP)")

        logger.info(f"Using LLM: {settings.llm_provider}")
        activity_logger.log_activity(f"Using LLM Provider: {settings.llm_provider}", "INFO")

        activity_logger.log_agent_start("Content Understanding Agent", "3")
        content = ContentUnderstandingAgent(db)
        content_results = content.process_batch(limit=3)  # Small batch for LLM
        logger.info(f"Content Analysis: {content_results}")

        cont_stats = content.get_statistics()
        logger.info(f"📊 NLP Stats: {cont_stats}")
        activity_logger.log_agent_success("Content Understanding Agent", content_results.get('processed', 0))

        # ===== PHASE 4: ENTITY MAPPING =====
        activity_logger.log_phase(4, "Entity Mapping (Agent 3)")
        print_section("PHASE 4: Entity Mapping (Agent 3)")

        activity_logger.log_agent_start("Entity Mapping Agent", "4")
        entities = EntityMappingAgent(db)
        entity_results = entities.process_batch(limit=3)
        logger.info(f"Entity Mapping: {entity_results}")

        ent_stats = entities.get_statistics()
        logger.info(f"📊 Entity Stats: {ent_stats}")
        activity_logger.log_agent_success("Entity Mapping Agent", entity_results.get('processed', 0))

        # ===== PHASE 5: MARKET REGIME DETECTION =====
        activity_logger.log_phase(5, "Market Regime Detection (Agent 5)")
        print_section("PHASE 5: Market Regime Detection (Agent 5)")

        activity_logger.log_agent_start("Regime Detection Agent", "5")
        regime = RegimeDetectionAgent(db)
        logger.info("Updating market regime...")
        activity_logger.log_activity("Detecting current market regime...", "PROCESSING")
        current_regime = regime.update_regime()
        logger.info(f"Current Regime: {current_regime.regime}")
        logger.info(f"VIX Level: {current_regime.regime_metadata.get('vix_level', 'N/A')}")
        activity_logger.log_activity(f"Regime: {current_regime.regime}", "SUCCESS")

        # ===== PHASE 6: SURPRISE QUANTIFICATION =====
        activity_logger.log_phase(6, "Surprise Quantification (Agent 4.5)")
        print_section("PHASE 6: Surprise Quantification (Agent 4.5)")

        activity_logger.log_agent_start("Surprise Quantification Agent", "6")
        surprise = SurpriseQuantificationAgent(db)
        surprise_results = surprise.process_batch(limit=10)
        logger.info(f"Surprise Analysis: {surprise_results}")

        surp_stats = surprise.get_statistics()
        logger.info(f"📊 Surprise Stats: {surp_stats}")
        activity_logger.log_agent_success("Surprise Quantification Agent", surprise_results.get('processed', 0))

        # ===== PHASE 7: IMPACT SCORING =====
        activity_logger.log_phase(7, "Impact Scoring (Agent 4)")
        print_section("PHASE 7: Impact Scoring (Agent 4)")

        activity_logger.log_agent_start("Impact Scoring Agent", "7")
        impact = ImpactScoringAgent(db)
        impact_results = impact.process_batch(limit=5)
        logger.info(f"Impact Scoring: {impact_results}")

        imp_stats = impact.get_statistics()
        logger.info(f"📊 Impact Stats: {imp_stats}")
        if imp_stats['top_impactful']:
            logger.info(f"Top Impactful News: {imp_stats['top_impactful'][:3]}")
        activity_logger.log_agent_success("Impact Scoring Agent", impact_results.get('processed', 0))

        # ===== PHASE 8: PREDICTION GENERATION =====
        activity_logger.log_phase(8, "Prediction Generation (Agent 6)")
        print_section("PHASE 8: Prediction Generation (Agent 6)")

        activity_logger.log_agent_start("Prediction Agent", "8")
        predictor = PredictionAgent(db)
        pred_results = predictor.process_batch(limit=5)
        logger.info(f"Prediction Generation: {pred_results}")

        pred_stats = predictor.get_statistics()
        logger.info(f"📊 Prediction Stats: {pred_stats}")
        activity_logger.log_agent_success("Prediction Agent", pred_results.get('generated', 0))

        # ===== FINAL SUMMARY =====
        end_time = datetime.now()
        duration = (end_time - start_time).total_seconds()

        print_section("PIPELINE COMPLETE - FINAL SUMMARY")
        logger.info(f"Duration: {duration:.1f} seconds")
        logger.info("")
        logger.info("📈 DATA PIPELINE:")
        logger.info(f"  - Raw Articles: {ing_stats['total_articles']}")
        logger.info(f"  - High Quality: {qual_stats.get('high_quality', 0)}")
        logger.info(f"  - NLP Processed: {cont_stats.get('total_processed', 0)}")
        logger.info(f"  - Entities Mapped: {ent_stats.get('total_entities', 0)}")
        logger.info("")
        logger.info("🔍 ANALYSIS:")
        logger.info(f"  - Surprises Found: {surp_stats.get('total_surprises', 0)}")
        logger.info(f"  - Impact Scores: {imp_stats.get('total_scores', 0)}")
        logger.info(f"  - High Impact: {imp_stats.get('high_impact', 0)}")
        logger.info("")
        logger.info("🎯 PREDICTIONS:")
        logger.info(f"  - Total Predictions: {pred_stats.get('total_predictions', 0)}")
        logger.info(f"  - Bullish: {pred_stats.get('bullish_predictions', 0)}")
        logger.info(f"  - Bearish: {pred_stats.get('bearish_predictions', 0)}")
        logger.info(f"  - Avg Confidence: {pred_stats.get('average_confidence', 0):.2f}")
        logger.info("")
        logger.info("🌡️  CURRENT MARKET REGIME:")
        logger.info(f"  {current_regime.regime}")
        logger.info("=" * 70)
        logger.info("\n✅ MVP PIPELINE COMPLETED SUCCESSFULLY!")
        logger.info(f"End Time: {end_time}")
        
        activity_logger.log_pipeline_complete("TradeMeUp MVP Pipeline", duration)

        activity_logger.log_pipeline_complete("TradeMeUp MVP Pipeline", duration)

    except Exception as e:
        logger.error(f"❌ Pipeline failed: {e}", exc_info=True)
        activity_logger.log_agent_error("Pipeline", str(e))
        raise
    finally:
        db.close()


if __name__ == "__main__":
    main()
