#!/usr/bin/env python3
"""
Backfill Script - Process all existing articles through all agents
Completes missing analyses for articles already in the database
Uses the same LLM settings (Ollama/OpenAI) as configured in environment
"""
import argparse
import sys
from datetime import datetime
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

import logging

from src.agents.content_understanding_agent import ContentUnderstandingAgent

# Import all agents
from src.agents.data_quality_agent import DataQualityAgent
from src.agents.entity_mapping_agent import EntityMappingAgent
from src.agents.fact_verification_agent import FactVerificationAgent
from src.agents.impact_scoring_agent import ImpactScoringAgent
from src.agents.prediction_agent import PredictionAgent
from src.agents.regime_detection_agent import RegimeDetectionAgent
from src.agents.surprise_quantification_agent import SurpriseQuantificationAgent

# Import settings to use environment configuration
from src.config.settings import settings
from src.models.analysis import FactVerification, ImpactScore, SurpriseScore
from src.models.data_quality import DataQualityScore
from src.models.database import SessionLocal
from src.models.entities import NewsEntityMapping
from src.models.processed_news import ProcessedNews
from src.models.raw_news import RawNews
from src.utils.redact import redact_url, set_status

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


def print_section(title):
    """Print formatted section"""
    print("\n" + "=" * 80)
    print(f"  {title}")
    print("=" * 80)


def print_llm_config():
    """Print current LLM configuration"""
    print_section("LLM Configuration")
    print(f"Provider: {settings.llm_provider}")

    if settings.llm_provider == "ollama":
        print(f"Ollama URL: {redact_url(settings.ollama_base_url)}")
        print(f"Ollama Model: {settings.ollama_model}")
    elif settings.llm_provider == "openai":
        print(f"OpenAI API Key: {set_status(settings.openai_api_key)}")
        print(f"OpenAI Model: {settings.openai_model}")
    elif settings.llm_provider == "anthropic":
        print(f"Anthropic API Key: {set_status(settings.anthropic_api_key)}")
        print(f"Anthropic Model: {settings.anthropic_model}")

    print(f"Database: {redact_url(settings.database_url)}")
    print()


def backfill_quality_assessment(db, batch_size=100):
    """Process all RawNews without quality scores"""
    print_section("Phase 1: Quality Assessment Backfill")

    # Count articles needing processing
    unassessed = db.query(RawNews).outerjoin(
        DataQualityScore, RawNews.news_id == DataQualityScore.news_id
    ).filter(DataQualityScore.news_id.is_(None)).count()

    logger.info(f"Articles needing quality assessment: {unassessed}")

    if unassessed == 0:
        logger.info("✓ All articles have quality scores")
        return 0

    agent = DataQualityAgent(db)
    processed = 0
    max_iterations = (unassessed // batch_size) + 2  # Allow some buffer
    iterations = 0

    while iterations < max_iterations:
        iterations += 1
        result = agent.process_batch(limit=batch_size)
        batch_processed = result.get('processed', 0)

        if batch_processed == 0:
            break

        processed += batch_processed
        logger.info(f"Progress: {processed}/{unassessed} articles assessed")

        # Commit periodically to prevent data loss
        if processed % (batch_size * 5) == 0:
            db.commit()
            logger.info("Database checkpoint committed")

    logger.info(f"✓ Completed quality assessment for {processed} articles")
    db.commit()  # Final commit for this phase
    return processed


def backfill_content_understanding(db, batch_size=50):
    """Process all quality-checked RawNews through NLP"""
    print_section("Phase 2: Content Understanding Backfill")

    # Count articles needing processing - must have quality score >= 0.6
    unprocessed = db.query(RawNews).join(
        DataQualityScore, RawNews.news_id == DataQualityScore.news_id
    ).filter(
        DataQualityScore.quality_score >= 0.6
    ).outerjoin(
        ProcessedNews, RawNews.news_id == ProcessedNews.news_id
    ).filter(ProcessedNews.news_id.is_(None)).count()

    logger.info(f"Articles needing NLP processing: {unprocessed}")

    if unprocessed == 0:
        logger.info("✓ All quality articles have been processed")
        return 0

    agent = ContentUnderstandingAgent(db)
    processed = 0
    errors = 0
    max_iterations = (unprocessed // batch_size) + 2
    iterations = 0

    while iterations < max_iterations:
        iterations += 1
        result = agent.process_batch(limit=batch_size)
        batch_processed = result.get('processed', 0)
        errors += result.get('errors', 0)

        if batch_processed == 0:
            break

        processed += batch_processed
        logger.info(f"Progress: {processed}/{unprocessed} articles analyzed (errors: {errors})")

        if processed % (batch_size * 5) == 0:
            db.commit()
            logger.info("Database checkpoint committed")

    logger.info(f"✓ Completed NLP for {processed} articles (errors: {errors})")
    db.commit()  # Final commit for this phase
    return processed


def backfill_entity_mapping(db, batch_size=30):
    """Process all ProcessedNews through entity mapping"""
    print_section("Phase 3: Entity Mapping Backfill")

    # Count articles needing processing
    unmapped = db.query(ProcessedNews).outerjoin(
        NewsEntityMapping, ProcessedNews.news_id == NewsEntityMapping.news_id
    ).filter(NewsEntityMapping.news_id.is_(None)).count()

    logger.info(f"Articles needing entity mapping: {unmapped}")

    if unmapped == 0:
        logger.info("✓ All processed articles have entity mappings")
        return 0

    agent = EntityMappingAgent(db)
    processed = 0

    while True:
        result = agent.process_batch(limit=batch_size)
        batch_processed = result.get('processed', 0)

        if batch_processed == 0:
            break

        processed += batch_processed
        mappings = result.get('total_mappings', 0)
        logger.info(f"Progress: {processed}/{unmapped} articles mapped ({mappings} mappings)")

    logger.info(f"✓ Completed entity mapping for {processed} articles")
    return processed


def backfill_fact_verification(db, batch_size=50):
    """Process all ProcessedNews through fact verification"""
    print_section("Phase 4: Fact Verification Backfill")

    # Count articles needing processing
    unverified = db.query(ProcessedNews).outerjoin(
        FactVerification, ProcessedNews.news_id == FactVerification.news_id
    ).filter(FactVerification.news_id.is_(None)).count()

    logger.info(f"Articles needing fact verification: {unverified}")

    if unverified == 0:
        logger.info("✓ All processed articles have been fact-checked")
        return 0

    agent = FactVerificationAgent(db)
    processed = 0
    max_iterations = (unverified // batch_size) + 2
    iterations = 0

    while iterations < max_iterations:
        iterations += 1
        result = agent.process_batch(limit=batch_size)
        batch_processed = result.get('processed', 0)

        if batch_processed == 0:
            break

        processed += batch_processed
        logger.info(f"Progress: {processed}/{unverified} articles verified")

        if processed % (batch_size * 5) == 0:
            db.commit()
            logger.info("Database checkpoint committed")

    logger.info(f"✓ Completed fact verification for {processed} articles")
    db.commit()  # Final commit for this phase
    return processed


def backfill_surprise_scoring(db, batch_size=50):
    """Process all ProcessedNews through surprise quantification"""
    print_section("Phase 5: Surprise Quantification Backfill")

    # Count articles needing processing
    unsurprised = db.query(ProcessedNews).outerjoin(
        SurpriseScore, ProcessedNews.news_id == SurpriseScore.news_id
    ).filter(SurpriseScore.news_id.is_(None)).count()

    logger.info(f"Articles needing surprise scoring: {unsurprised}")

    if unsurprised == 0:
        logger.info("✓ All processed articles have surprise scores")
        return 0

    # Note: SurpriseQuantificationAgent uses scoped sessions internally
    agent = SurpriseQuantificationAgent()
    processed = 0
    total_surprises = 0
    max_iterations = (unsurprised // batch_size) + 2
    iterations = 0

    while iterations < max_iterations:
        iterations += 1
        result = agent.process_batch(limit=batch_size)
        batch_processed = result.get('processed', 0)

        if batch_processed == 0:
            break

        processed += batch_processed
        total_surprises += result.get('surprises_found', 0)
        logger.info(f"Progress: {processed}/{unsurprised} articles scored ({total_surprises} surprises found)")

        if processed % (batch_size * 5) == 0:
            db.commit()
            logger.info("Database checkpoint committed")

    logger.info(f"✓ Completed surprise scoring for {processed} articles ({total_surprises} surprises found)")
    db.commit()  # Final commit for this phase
    return processed


def backfill_impact_scoring(db, batch_size=50):
    """Process all ProcessedNews with entities through impact scoring"""
    print_section("Phase 6: Impact Scoring Backfill")

    # Count articles needing processing
    unscored = db.query(ProcessedNews).outerjoin(
        ImpactScore, ProcessedNews.news_id == ImpactScore.news_id
    ).filter(ImpactScore.news_id.is_(None)).count()

    logger.info(f"Articles needing impact scoring: {unscored}")

    if unscored == 0:
        logger.info("✓ All processed articles have impact scores")
        return 0

    # Note: ImpactScoringAgent uses scoped sessions internally
    agent = ImpactScoringAgent()
    processed = 0
    total_scores = 0
    max_iterations = (unscored // batch_size) + 2
    iterations = 0

    while iterations < max_iterations:
        iterations += 1
        result = agent.process_batch(limit=batch_size)
        batch_processed = result.get('processed', 0)

        if batch_processed == 0:
            break

        processed += batch_processed
        total_scores += result.get('impact_scores', 0)
        logger.info(f"Progress: {processed}/{unscored} articles scored ({total_scores} impact scores created)")

        if processed % (batch_size * 5) == 0:
            db.commit()
            logger.info("Database checkpoint committed")

    logger.info(f"✓ Completed impact scoring for {processed} articles")
    db.commit()  # Final commit for this phase
    return processed


def backfill_predictions(db, batch_size=50):
    """Generate predictions for high-impact scores"""
    print_section("Phase 7: Prediction Generation Backfill")

    # Count impact scores needing predictions
    from src.models.analysis import ImpactScore
    from src.models.predictions import Prediction

    # Get all high-impact scores
    high_impact = db.query(ImpactScore).filter(
        ImpactScore.impact_score >= 0.4
    ).count()

    logger.info(f"High-impact scores in database: {high_impact}")

    # Estimate how many need predictions (rough estimate)
    existing_predictions = db.query(Prediction).count()
    logger.info(f"Existing predictions: {existing_predictions}")

    if high_impact == 0:
        logger.info("✓ No high-impact scores to predict")
        return 0

    # Note: PredictionAgent uses scoped sessions internally, no db param needed
    agent = PredictionAgent()
    total_processed = 0
    total_predictions = 0
    max_iterations = (high_impact // batch_size) + 10  # Buffer for safety
    iterations = 0

    # Run until no more predictions needed
    while iterations < max_iterations:
        iterations += 1
        result = agent.process_batch(limit=batch_size)
        batch_processed = result.get('processed', 0)
        batch_predictions = result.get('predictions_created', 0)

        if batch_processed == 0:
            break

        total_processed += batch_processed
        total_predictions += batch_predictions
        logger.info(f"Progress: {total_processed} scores processed, {total_predictions} predictions generated")

        # Commit periodically to prevent data loss
        if total_processed % (batch_size * 5) == 0:
            db.commit()
            logger.info("Database checkpoint committed")

    logger.info(f"✓ Completed prediction generation: {total_processed} scores processed, {total_predictions} predictions created")
    db.commit()  # Final commit for this phase
    return total_processed


def update_market_regime(db):
    """Update current market regime"""
    print_section("Phase 8: Market Regime Update")

    agent = RegimeDetectionAgent(db)
    regime = agent.update_regime()

    logger.info(f"✓ Current market regime: {regime.regime}")
    logger.info(f"  Metadata: {regime.regime_metadata}")
    return 1


def main():
    """Run complete backfill process"""
    parser = argparse.ArgumentParser(description='Backfill missing analyses for existing articles')
    parser.add_argument('--skip-quality', action='store_true', help='Skip quality assessment')
    parser.add_argument('--skip-content', action='store_true', help='Skip content understanding')
    parser.add_argument('--skip-entities', action='store_true', help='Skip entity mapping')
    parser.add_argument('--skip-facts', action='store_true', help='Skip fact verification')
    parser.add_argument('--skip-surprises', action='store_true', help='Skip surprise scoring')
    parser.add_argument('--skip-impact', action='store_true', help='Skip impact scoring')
    parser.add_argument('--skip-predictions', action='store_true', help='Skip predictions')
    parser.add_argument('--batch-size', type=int, default=50, help='Batch size for processing')

    args = parser.parse_args()

    start_time = datetime.now()

    print("=" * 80)
    print("  TradeMeUp - Complete Backfill Process")
    print("  Processing all existing articles through all agents")
    print("=" * 80)
    print(f"Start time: {start_time}")

    # Print LLM configuration
    print_llm_config()

    db = SessionLocal()

    try:
        # Run all backfill phases
        stats = {}

        if not args.skip_quality:
            stats['quality'] = backfill_quality_assessment(db, batch_size=args.batch_size)
        else:
            logger.info("Skipping quality assessment")
            stats['quality'] = 0

        if not args.skip_content:
            stats['content'] = backfill_content_understanding(db, batch_size=args.batch_size)
        else:
            logger.info("Skipping content understanding")
            stats['content'] = 0

        if not args.skip_entities:
            stats['entities'] = backfill_entity_mapping(db, batch_size=30)
        else:
            logger.info("Skipping entity mapping")
            stats['entities'] = 0

        if not args.skip_facts:
            stats['facts'] = backfill_fact_verification(db, batch_size=args.batch_size)
        else:
            logger.info("Skipping fact verification")
            stats['facts'] = 0

        if not args.skip_surprises:
            stats['surprises'] = backfill_surprise_scoring(db, batch_size=args.batch_size)
        else:
            logger.info("Skipping surprise scoring")
            stats['surprises'] = 0

        if not args.skip_impact:
            stats['impact'] = backfill_impact_scoring(db, batch_size=args.batch_size)
        else:
            logger.info("Skipping impact scoring")
            stats['impact'] = 0

        if not args.skip_predictions:
            stats['predictions'] = backfill_predictions(db, batch_size=args.batch_size)
        else:
            logger.info("Skipping predictions")
            stats['predictions'] = 0

        stats['regime'] = update_market_regime(db)

        # Final summary
        end_time = datetime.now()
        duration = (end_time - start_time).total_seconds()

        print_section("BACKFILL COMPLETE - SUMMARY")
        print(f"Duration: {duration:.1f} seconds ({duration/60:.1f} minutes)")
        print()
        print("Articles Processed:")
        print(f"  Quality Assessment:     {stats['quality']}")
        print(f"  Content Understanding:  {stats['content']}")
        print(f"  Entity Mapping:         {stats['entities']}")
        print(f"  Fact Verification:      {stats['facts']}")
        print(f"  Surprise Scoring:       {stats['surprises']}")
        print(f"  Impact Scoring:         {stats['impact']}")
        print(f"  Predictions:            {stats['predictions']}")
        print()
        print("✓ All backfill operations completed successfully!")
        print("=" * 80)

    except Exception as e:
        logger.error(f"Backfill failed: {e}", exc_info=True)
        raise
    finally:
        db.close()


if __name__ == "__main__":
    main()
