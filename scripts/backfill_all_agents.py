#!/usr/bin/env python3
"""
Backfill Script - Process all existing articles through all agents
Completes missing analyses for articles already in the database
Uses the same LLM settings (Ollama/OpenAI) as configured in environment

Every phase does the same thing: count what is still missing, then drive the
owning agent's ``process_batch`` until it stops making progress. That shape is
described once in :func:`run_phase`; the phases themselves are just data in
:data:`PHASES`.
"""
import argparse
import logging
import sys
from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from sqlalchemy.orm import Session

from src.agents import build_agent
from src.agents.content_understanding_agent import ContentUnderstandingAgent
from src.agents.data_quality_agent import DataQualityAgent
from src.agents.entity_mapping_agent import EntityMappingAgent
from src.agents.fact_verification_agent import FactVerificationAgent
from src.agents.impact_scoring_agent import ImpactScoringAgent
from src.agents.prediction_agent import PredictionAgent
from src.agents.regime_detection_agent import RegimeDetectionAgent
from src.agents.surprise_quantification_agent import SurpriseQuantificationAgent
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

# Articles below this quality score are not worth running NLP over.
MIN_QUALITY_FOR_CONTENT = 0.6

# Only impact scores at or above this level get a prediction.
MIN_IMPACT_FOR_PREDICTION = 0.4

# Safety margin on the iteration cap, so a phase whose agent keeps reporting
# progress on the same rows cannot spin forever.
ITERATION_BUFFER = 2


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


# --------------------------------------------------------------------------
# Pending-work queries
#
# Each returns how many rows still need this phase, which drives both the
# "nothing to do" short-circuit and the iteration cap.
# --------------------------------------------------------------------------

def _count_without_quality(db: Session) -> int:
    return db.query(RawNews).outerjoin(
        DataQualityScore, RawNews.news_id == DataQualityScore.news_id
    ).filter(DataQualityScore.news_id.is_(None)).count()


def _count_without_content(db: Session) -> int:
    return db.query(RawNews).join(
        DataQualityScore, RawNews.news_id == DataQualityScore.news_id
    ).filter(
        DataQualityScore.quality_score >= MIN_QUALITY_FOR_CONTENT
    ).outerjoin(
        ProcessedNews, RawNews.news_id == ProcessedNews.news_id
    ).filter(ProcessedNews.news_id.is_(None)).count()


def _count_missing(db: Session, related_model) -> int:
    """Count ProcessedNews rows that have no matching row in ``related_model``."""
    return db.query(ProcessedNews).outerjoin(
        related_model, ProcessedNews.news_id == related_model.news_id
    ).filter(related_model.news_id.is_(None)).count()


def _count_predictable_impacts(db: Session) -> int:
    """High-impact scores are the input to prediction generation.

    This counts all of them rather than only the unpredicted ones: there is no
    cheap join for "already predicted", and the agent skips what it has already
    handled. The number is used for progress display and the iteration cap.
    """
    return db.query(ImpactScore).filter(
        ImpactScore.impact_score >= MIN_IMPACT_FOR_PREDICTION
    ).count()


# --------------------------------------------------------------------------
# Phase table
# --------------------------------------------------------------------------

@dataclass(frozen=True)
class BackfillPhase:
    """One backfill phase: what to count, which agent to drive, how to say it."""

    key: str                                  # stats key and --skip-<key> flag
    title: str                                # section header
    label: str                                # summary table label
    noun: str                                 # e.g. "articles assessed"
    agent_class: type
    count_pending: Callable[[Session], int]
    batch_size: int | None = None             # overrides the CLI default
    # Optional secondary tally pulled out of each process_batch result,
    # e.g. ('surprises_found', 'surprises found').
    extra: tuple[str, str] | None = None


PHASES: list[BackfillPhase] = [
    BackfillPhase(
        key='quality',
        title='Phase 1: Quality Assessment Backfill',
        label='Quality Assessment',
        noun='articles assessed',
        agent_class=DataQualityAgent,
        count_pending=_count_without_quality,
        batch_size=100,
    ),
    BackfillPhase(
        key='content',
        title='Phase 2: Content Understanding Backfill',
        label='Content Understanding',
        noun='articles analyzed',
        agent_class=ContentUnderstandingAgent,
        count_pending=_count_without_content,
    ),
    BackfillPhase(
        key='entities',
        title='Phase 3: Entity Mapping Backfill',
        label='Entity Mapping',
        noun='articles mapped',
        agent_class=EntityMappingAgent,
        count_pending=lambda db: _count_missing(db, NewsEntityMapping),
        batch_size=30,
        extra=('total_mappings', 'mappings'),
    ),
    BackfillPhase(
        key='facts',
        title='Phase 4: Fact Verification Backfill',
        label='Fact Verification',
        noun='articles verified',
        agent_class=FactVerificationAgent,
        count_pending=lambda db: _count_missing(db, FactVerification),
    ),
    BackfillPhase(
        key='surprises',
        title='Phase 5: Surprise Quantification Backfill',
        label='Surprise Scoring',
        noun='articles scored',
        agent_class=SurpriseQuantificationAgent,
        count_pending=lambda db: _count_missing(db, SurpriseScore),
        extra=('surprises_found', 'surprises found'),
    ),
    BackfillPhase(
        key='impact',
        title='Phase 6: Impact Scoring Backfill',
        label='Impact Scoring',
        noun='articles scored',
        agent_class=ImpactScoringAgent,
        count_pending=lambda db: _count_missing(db, ImpactScore),
        # The agent reports this as 'total_scores'; the previous code read a
        # non-existent 'impact_scores' key, so the tally always showed 0.
        extra=('total_scores', 'impact scores created'),
    ),
    BackfillPhase(
        key='predictions',
        title='Phase 7: Prediction Generation Backfill',
        label='Predictions',
        noun='scores processed',
        agent_class=PredictionAgent,
        count_pending=_count_predictable_impacts,
        extra=('predictions_created', 'predictions generated'),
    ),
]


def run_phase(phase: BackfillPhase, db: Session, default_batch_size: int) -> int:
    """Drive one phase's agent until it stops making progress.

    Returns the number of rows the agent reported processing. The agents own
    their own sessions and commit as they go, so ``db`` is only used to count
    the outstanding work.
    """
    print_section(phase.title)

    batch_size = phase.batch_size or default_batch_size
    pending = phase.count_pending(db)
    logger.info(f"Rows needing {phase.label.lower()}: {pending}")

    if pending == 0:
        logger.info(f"✓ Nothing outstanding for {phase.label.lower()}")
        return 0

    agent = build_agent(phase.agent_class, db)
    processed = 0
    errors = 0
    extra_total = 0

    # A batch that processes nothing means the agent is done, but cap the loop
    # regardless so a misreporting agent cannot spin forever.
    max_iterations = (pending // batch_size) + ITERATION_BUFFER

    for _ in range(max_iterations):
        result = agent.process_batch(limit=batch_size)

        batch_processed = result.get('processed', 0)
        if batch_processed == 0:
            break

        processed += batch_processed
        errors += result.get('errors', 0)

        progress = f"Progress: {processed}/{pending} {phase.noun}"
        if phase.extra:
            extra_total += result.get(phase.extra[0], 0)
            progress += f" ({extra_total} {phase.extra[1]})"
        if errors:
            progress += f" (errors: {errors})"
        logger.info(progress)

    summary = f"✓ Completed {phase.label.lower()} for {processed} rows"
    if phase.extra:
        summary += f" ({extra_total} {phase.extra[1]})"
    if errors:
        summary += f" (errors: {errors})"
    logger.info(summary)

    return processed


def update_market_regime(db: Session) -> int:
    """Update current market regime"""
    print_section("Phase 8: Market Regime Update")

    agent = RegimeDetectionAgent(db)
    regime = agent.update_regime()

    logger.info(f"✓ Current market regime: {regime.regime}")
    logger.info(f"  Metadata: {regime.regime_metadata}")
    return 1


def build_parser() -> argparse.ArgumentParser:
    """Build the CLI, deriving one --skip-<phase> flag per entry in PHASES."""
    parser = argparse.ArgumentParser(
        description='Backfill missing analyses for existing articles'
    )
    for phase in PHASES:
        parser.add_argument(
            f'--skip-{phase.key}',
            action='store_true',
            help=f'Skip {phase.label.lower()}',
        )
    parser.add_argument(
        '--batch-size', type=int, default=50, help='Batch size for processing'
    )
    return parser


def main():
    """Run complete backfill process"""
    args = build_parser().parse_args()

    start_time = datetime.now()

    print("=" * 80)
    print("  TradeMeUp - Complete Backfill Process")
    print("  Processing all existing articles through all agents")
    print("=" * 80)
    print(f"Start time: {start_time}")

    print_llm_config()

    try:
        with SessionLocal() as db:
            stats = {}

            for phase in PHASES:
                if getattr(args, f'skip_{phase.key}'):
                    logger.info(f"Skipping {phase.label.lower()}")
                    stats[phase.key] = 0
                    continue
                stats[phase.key] = run_phase(phase, db, args.batch_size)

            stats['regime'] = update_market_regime(db)

        duration = (datetime.now() - start_time).total_seconds()

        print_section("BACKFILL COMPLETE - SUMMARY")
        print(f"Duration: {duration:.1f} seconds ({duration/60:.1f} minutes)")
        print()
        print("Rows Processed:")
        width = max(len(phase.label) for phase in PHASES) + 2
        for phase in PHASES:
            print(f"  {phase.label + ':':<{width}} {stats[phase.key]}")
        print()
        print("✓ All backfill operations completed successfully!")
        print("=" * 80)

    except Exception as e:
        logger.error(f"Backfill failed: {e}", exc_info=True)
        raise


if __name__ == "__main__":
    main()
