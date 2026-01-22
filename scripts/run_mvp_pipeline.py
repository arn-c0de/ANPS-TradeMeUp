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

    print_section("TradeMeUp MVP Pipeline - Complete Run")
    logger.info(f"Start Time: {start_time}")
    logger.info(f"LLM Provider: {settings.llm_provider}")
    logger.info(f"Database: {settings.database_url}")

    # Create database session
    db = SessionLocal()

    try:
        # ===== PHASE 1: DATA COLLECTION =====
        print_section("PHASE 1: Data Collection (Agent 1)")

        ingestion = IngestionAgent(db)

        # Fetch from RSS feeds
        logger.info("Fetching from RSS feeds...")
        rss_results = ingestion.fetch_all_rss_feeds()
        logger.info(f"RSS Results: {rss_results}")

        # Fetch from News API (if available)
        if settings.news_api_key:
            logger.info("Fetching from News API...")
            api_count = ingestion.fetch_news_api(settings.news_api_key)
            logger.info(f"News API: {api_count} new articles")

        ing_stats = ingestion.get_statistics()
        logger.info(f"📊 Total articles in DB: {ing_stats['total_articles']}")

        # ===== PHASE 2: QUALITY ASSESSMENT =====
        print_section("PHASE 2: Quality Assessment (Agent 1.5)")

        quality = DataQualityAgent(db)
        quality_results = quality.process_batch(limit=50)
        logger.info(f"Quality Results: {quality_results}")

        qual_stats = quality.get_statistics()
        logger.info(f"📊 Quality Stats: {qual_stats}")

        # ===== PHASE 3: CONTENT UNDERSTANDING =====
        print_section("PHASE 3: Content Understanding (Agent 2 - NLP)")

        logger.info(f"Using LLM: {settings.llm_provider}")

        content = ContentUnderstandingAgent(db)
        content_results = content.process_batch(limit=3)  # Small batch for LLM
        logger.info(f"Content Analysis: {content_results}")

        cont_stats = content.get_statistics()
        logger.info(f"📊 NLP Stats: {cont_stats}")

        # ===== PHASE 4: ENTITY MAPPING =====
        print_section("PHASE 4: Entity Mapping (Agent 3)")

        entities = EntityMappingAgent(db)
        entity_results = entities.process_batch(limit=3)
        logger.info(f"Entity Mapping: {entity_results}")

        ent_stats = entities.get_statistics()
        logger.info(f"📊 Entity Stats: {ent_stats}")

        # ===== PHASE 5: MARKET REGIME DETECTION =====
        print_section("PHASE 5: Market Regime Detection (Agent 5)")

        regime = RegimeDetectionAgent(db)
        logger.info("Updating market regime...")
        current_regime = regime.update_regime()
        logger.info(f"Current Regime: {current_regime.regime}")
        logger.info(f"VIX Level: {current_regime.regime_metadata.get('vix_level', 'N/A')}")

        # ===== PHASE 6: SURPRISE QUANTIFICATION =====
        print_section("PHASE 6: Surprise Quantification (Agent 4.5)")

        surprise = SurpriseQuantificationAgent(db)
        surprise_results = surprise.process_batch(limit=10)
        logger.info(f"Surprise Analysis: {surprise_results}")

        surp_stats = surprise.get_statistics()
        logger.info(f"📊 Surprise Stats: {surp_stats}")

        # ===== PHASE 7: IMPACT SCORING =====
        print_section("PHASE 7: Impact Scoring (Agent 4)")

        impact = ImpactScoringAgent(db)
        impact_results = impact.process_batch(limit=5)
        logger.info(f"Impact Scoring: {impact_results}")

        imp_stats = impact.get_statistics()
        logger.info(f"📊 Impact Stats: {imp_stats}")
        if imp_stats['top_impactful']:
            logger.info(f"Top Impactful News: {imp_stats['top_impactful'][:3]}")

        # ===== PHASE 8: PREDICTION GENERATION =====
        print_section("PHASE 8: Prediction Generation (Agent 6)")

        predictor = PredictionAgent(db)
        pred_results = predictor.process_batch(limit=5)
        logger.info(f"Prediction Generation: {pred_results}")

        pred_stats = predictor.get_statistics()
        logger.info(f"📊 Prediction Stats: {pred_stats}")

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

    except Exception as e:
        logger.error(f"❌ Pipeline failed: {e}", exc_info=True)
        raise
    finally:
        db.close()


if __name__ == "__main__":
    main()
