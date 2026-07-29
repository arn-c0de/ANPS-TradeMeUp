"""
Continuous Pipeline Runner
Runs the pipeline continuously in the background, checking for new articles periodically

Performance & Hardening Features:
- Graceful shutdown with signal handling
- Exponential backoff on errors
- Memory monitoring and limits
- Dynamic batch sizing
- Connection pooling
- Performance metrics
"""
import logging
import signal
import sys
import time
from collections import deque
from collections.abc import Mapping
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path

import psutil

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from src.agents import build_agent
from src.agents.ab_testing_agent import ABTestingAgent
from src.agents.confidence_calibration_agent import ConfidenceCalibrationAgent
from src.agents.content_understanding_agent import ContentUnderstandingAgent
from src.agents.correlation_analysis_agent import CorrelationAnalysisAgent
from src.agents.data_quality_agent import DataQualityAgent
from src.agents.entity_mapping_agent import EntityMappingAgent

# NEW AGENTS from Phase 2
from src.agents.fact_verification_agent import FactVerificationAgent
from src.agents.impact_scoring_agent import ImpactScoringAgent
from src.agents.ingestion_agent import IngestionAgent
from src.agents.meta_strategy_agent import MetaStrategyAgent
from src.agents.model_performance_monitor import ModelPerformanceMonitor
from src.agents.prediction_agent import PredictionAgent
from src.agents.regime_detection_agent import RegimeDetectionAgent
from src.agents.scenario_generation_agent import ScenarioGenerationAgent
from src.agents.signal_decay_agent import SignalDecayAgent
from src.agents.surprise_quantification_agent import SurpriseQuantificationAgent
from src.agents.trading_simulation_agent import TradingSimulationAgent
from src.config.settings import settings
from src.models.database import SessionLocal
from src.models.processed_news import ProcessedNews
from src.models.raw_news import RawNews
from src.models.system_logs import SystemLog
from src.utils.activity_logger import activity_logger

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Starting batch size per phase, and the ceiling each may grow to when
# iterations are running comfortably. Both are keyed by a phase's `batch_key`.
INITIAL_BATCH_SIZES = {
    'quality': 50,
    'content': 30,
    'entity': 20,
    'surprise': 30,
    'impact': 30,
    'decay': 50,
    'prediction': 50,
    'simulation': 50,
    'fact_verification': 30,
    'correlation': 10,   # Lower because it's computation-heavy
    'calibration': 20,
    'meta_strategy': 10,  # Creates ensemble predictions
    'scenarios': 5,
}

MAX_BATCH_SIZES = {
    'quality': 100,
    'content': 50,
    'entity': 30,
    'surprise': 50,
    'impact': 50,
    'decay': 100,
    'prediction': 100,
    'simulation': 100,
    'fact_verification': 50,
    'correlation': 20,
    'calibration': 30,
    'meta_strategy': 20,
    # Bounded by the number of defined scenario types, so growing past it
    # would be a no-op.
    'scenarios': 5,
}

DEFAULT_MAX_BATCH_SIZE = 50
MIN_BATCH_SIZE = 5

# Only impact scores at or above this level get a prediction, one per horizon.
MIN_IMPACT_FOR_PREDICTION = 0.4
PREDICTION_HORIZONS = ('1d', '5d', '20d')

# Brief pause between iterations while a backlog is still being worked off.
BACKLOG_PAUSE_SECONDS = 2

# An iteration slower than this shrinks batches; faster than SPEEDUP_SECONDS
# (with no recent errors) grows them.
SLOWDOWN_SECONDS = 300
SPEEDUP_SECONDS = 120


@dataclass(frozen=True)
class PipelinePhase:
    """One step of a pipeline iteration.

    Every phase does the same thing - check for a stop request, announce
    itself, drive one agent method, log the result - so that shape lives once
    in :meth:`ContinuousPipeline._run_phase` and the phases are just data.
    """

    number: float
    name: str                                   # shown in the activity log
    agent_class: type | None = None
    method: str = 'process_batch'
    batch_key: str | None = None                # key into self.batch_sizes
    kwargs: Mapping[str, object] = field(default_factory=dict)
    setting: str | None = None                  # settings flag gating this phase
    handler: str | None = None                  # ContinuousPipeline method instead of an agent
    optional: bool = False                      # failure warns instead of aborting


# Ordered pipeline. `process_batch` is what actually writes records; a phase
# that calls `get_statistics` only reports on work someone else did.
PHASES: tuple[PipelinePhase, ...] = (
    PipelinePhase(1, 'Data Ingestion', IngestionAgent, method='fetch_all_rss_feeds'),
    PipelinePhase(2, 'Quality Assessment', DataQualityAgent, batch_key='quality'),
    PipelinePhase(3, 'Content Analysis', ContentUnderstandingAgent, batch_key='content'),
    PipelinePhase(4, 'Entity Mapping', EntityMappingAgent, batch_key='entity'),
    PipelinePhase(5, 'Market Regime', RegimeDetectionAgent, method='update_regime'),
    PipelinePhase(6, 'Surprise Quantification', SurpriseQuantificationAgent,
                  batch_key='surprise'),
    PipelinePhase(7, 'Impact Scoring', ImpactScoringAgent, batch_key='impact'),
    # Phases 8 and 9 called get_statistics(), which only counts existing rows.
    # No decay model and no entity correlation was ever created by the
    # pipeline, so both counts stayed at zero forever.
    PipelinePhase(8, 'Signal Decay Modeling', SignalDecayAgent, batch_key='decay'),
    PipelinePhase(9, 'Correlation Analysis', CorrelationAnalysisAgent,
                  batch_key='correlation'),
    PipelinePhase(10, 'Predictions', PredictionAgent, batch_key='prediction'),
    PipelinePhase(10.5, 'Auto-Processing Predictions',
                  handler='_auto_process_predictions', optional=True),
    PipelinePhase(11, 'Trading Simulation', TradingSimulationAgent,
                  batch_key='simulation', kwargs={'lookback_days': 7}),
    PipelinePhase(12, 'Scenario Generation', ScenarioGenerationAgent,
                  batch_key='scenarios', setting='enable_scenarios'),
    PipelinePhase(13, 'Fact Verification', FactVerificationAgent,
                  batch_key='fact_verification', setting='enable_fact_checking'),
    PipelinePhase(14, 'Confidence Calibration', ConfidenceCalibrationAgent,
                  batch_key='calibration', setting='enable_calibration'),
    PipelinePhase(15, 'Meta-Strategy Ensemble', MetaStrategyAgent,
                  batch_key='meta_strategy', setting='enable_meta_strategy'),
    # Reporting-only phases: these two genuinely just summarise past results.
    PipelinePhase(16, 'Performance Monitoring', ModelPerformanceMonitor,
                  method='get_statistics'),
    PipelinePhase(17, 'A/B Testing', ABTestingAgent, method='get_statistics'),
)

# Attach DB log handler so pipeline logs appear in the dashboard log viewer
try:
    from src.utils.db_log_handler import attach_db_handler as _attach
    _attach(source="pipeline")
except Exception:
    pass


class ContinuousPipeline:
    """Continuously running pipeline for production mode with performance optimization"""

    def __init__(self, check_interval: int = 300, max_memory_mb: int = 2048):
        """
        Initialize continuous pipeline
        
        Args:
            check_interval: Seconds between pipeline runs (default: 300 = 5 minutes)
            max_memory_mb: Maximum memory usage in MB before forcing garbage collection
        """
        self.check_interval = check_interval
        self.max_memory_mb = max_memory_mb
        self.running = False
        self.db: object | None = None
        self.started_at_utc: datetime | None = None

        # Performance metrics
        self.iteration_times = deque(maxlen=20)  # Last 20 iteration times
        self.error_count = 0
        self.consecutive_errors = 0
        self.backoff_time = 5  # Initial backoff time in seconds

        # Dynamic batch sizes (will be adjusted based on performance)
        self.batch_sizes = dict(INITIAL_BATCH_SIZES)

        # Setup signal handlers for graceful shutdown
        signal.signal(signal.SIGINT, self._signal_handler)
        signal.signal(signal.SIGTERM, self._signal_handler)

        # Display pipeline phase configuration
        self._display_phase_configuration()

        logger.info(f"Pipeline initialized with max_memory={max_memory_mb}MB, check_interval={check_interval}s")

    def _display_phase_configuration(self):
        """Display which pipeline phases are enabled/disabled"""
        logger.info("=" * 80)
        logger.info("Pipeline Phase Configuration")
        logger.info("=" * 80)

        enabled_phases = []
        disabled_phases = []

        # Derived from PHASES so a newly gated phase shows up here on its own.
        for phase in PHASES:
            if phase.setting is None:
                continue
            label = f"Phase {phase.number:g}: {phase.name}"
            if self._phase_is_enabled(phase):
                enabled_phases.append(label)
            else:
                disabled_phases.append(label)

        if enabled_phases:
            logger.info("✅ ENABLED Phases:")
            for phase in enabled_phases:
                logger.info(f"   • {phase}")

        if disabled_phases:
            logger.info("❌ DISABLED Phases (skipped to save tokens/resources):")
            for phase in disabled_phases:
                logger.info(f"   • {phase}")

        if not enabled_phases and not disabled_phases:
            logger.info("⚠️  No phase configuration found")

        logger.info("=" * 80)

    def _signal_handler(self, signum, frame):
        """Handle shutdown signals gracefully"""
        logger.info(f"Received signal {signum}, initiating graceful shutdown...")
        activity_logger.log_activity(f"Shutdown signal received: {signum}", "WARNING")
        self.stop()

    def _check_memory(self) -> float:
        """Check current memory usage and trigger GC if needed"""
        process = psutil.Process()
        memory_mb = process.memory_info().rss / 1024 / 1024

        if memory_mb > self.max_memory_mb:
            logger.warning(f"Memory usage {memory_mb:.1f}MB exceeds limit {self.max_memory_mb}MB, forcing GC")
            import gc
            gc.collect()
            memory_mb = process.memory_info().rss / 1024 / 1024
            logger.info(f"Post-GC memory: {memory_mb:.1f}MB")

        return memory_mb

    def _adjust_batch_sizes(self, duration: float):
        """Dynamically adjust batch sizes based on iteration performance"""
        if duration > SLOWDOWN_SECONDS:
            for key, size in self.batch_sizes.items():
                self.batch_sizes[key] = max(MIN_BATCH_SIZE, int(size * 0.8))
            logger.info(f"Reduced batch sizes due to slow iteration: {self.batch_sizes}")

        elif duration < SPEEDUP_SECONDS and self.consecutive_errors == 0:
            for key, size in self.batch_sizes.items():
                ceiling = MAX_BATCH_SIZES.get(key, DEFAULT_MAX_BATCH_SIZE)
                self.batch_sizes[key] = min(ceiling, int(size * 1.2))
            logger.info(f"Increased batch sizes due to good performance: {self.batch_sizes}")

    def _get_avg_iteration_time(self) -> float:
        """Calculate average iteration time from recent history"""
        if not self.iteration_times:
            return 0.0
        return sum(self.iteration_times) / len(self.iteration_times)

    def _stop_requested_via_db(self) -> bool:
        """Check whether the GUI requested a stop through the shared DB log table."""
        if self.started_at_utc is None:
            return False

        try:
            with SessionLocal() as db:
                request = (
                    db.query(SystemLog)
                    .filter(
                        SystemLog.source == "control",
                        SystemLog.component == "continuous_pipeline",
                        SystemLog.message == "STOP_REQUEST",
                        SystemLog.timestamp >= self.started_at_utc,
                    )
                    .order_by(SystemLog.timestamp.desc())
                    .first()
                )
        except Exception as exc:
            logger.debug(f"Failed to read external stop request: {exc}")
            return False

        return request is not None

    def _check_for_external_stop(self):
        """Stop the worker when the GUI sends a shared stop request."""
        if self._stop_requested_via_db():
            logger.info("External stop request detected from GUI control.")
            activity_logger.log_activity("Continuous Pipeline stop request acknowledged", "INFO")
            self.stop()
            raise KeyboardInterrupt

    def _sleep_with_stop_check(self, seconds: int):
        """Sleep in short chunks so stop requests are handled quickly."""
        remaining = max(0, int(seconds))
        while self.running and remaining > 0:
            self._check_for_external_stop()
            chunk = min(2, remaining)
            time.sleep(chunk)
            remaining -= chunk
        self._check_for_external_stop()

    def run(self):
        """Run the pipeline continuously with performance monitoring"""
        self.running = True
        self.started_at_utc = datetime.now(UTC)
        activity_logger.log_activity("Continuous Pipeline Mode STARTED", "SUCCESS")
        logger.info(f"Starting continuous pipeline (check every {self.check_interval}s)")

        iteration = 0

        while self.running:
            try:
                self._check_for_external_stop()
                iteration += 1
                start_time = datetime.now()

                # Check memory before iteration
                memory_before = self._check_memory()

                logger.info("=" * 60)
                logger.info(f"Pipeline Iteration #{iteration} - {start_time}")
                logger.info(f"Memory: {memory_before:.1f}MB | Avg Time: {self._get_avg_iteration_time():.1f}s | Batch Sizes: {self.batch_sizes}")
                logger.info("=" * 60)

                activity_logger.log_activity(f"Starting Pipeline Iteration #{iteration}", "INFO")

                # Create fresh database session with retry logic
                max_retries = 3
                for attempt in range(max_retries):
                    try:
                        self.db = SessionLocal()
                        break
                    except Exception as db_error:
                        if attempt < max_retries - 1:
                            wait_time = 2 ** attempt
                            logger.warning(f"DB connection failed (attempt {attempt+1}/{max_retries}), retrying in {wait_time}s...")
                            time.sleep(wait_time)
                        else:
                            raise

                # Verify DB session was created successfully
                if self.db is None:
                    raise RuntimeError("Database session is None - failed to create connection")

                # Run all pipeline phases
                new_articles = self._run_pipeline_iteration()
                self._check_for_external_stop()

                # Close database session safely
                if self.db:
                    try:
                        self.db.close()
                    except Exception as e:
                        logger.error(f"Error closing DB session: {e}")
                    finally:
                        self.db = None

                # Track performance metrics
                duration = (datetime.now() - start_time).total_seconds()
                self.iteration_times.append(duration)
                self.consecutive_errors = 0  # Reset error counter on success
                self.backoff_time = 5  # Reset backoff time

                # Check memory after iteration
                memory_after = self._check_memory()
                memory_delta = memory_after - memory_before

                logger.info(f"Iteration #{iteration} completed in {duration:.1f}s (avg: {self._get_avg_iteration_time():.1f}s)")
                logger.info(f"Memory delta: {memory_delta:+.1f}MB (now: {memory_after:.1f}MB)")
                activity_logger.log_activity(f"Iteration #{iteration} completed in {duration:.1f}s", "SUCCESS")

                # Adjust batch sizes based on performance
                self._adjust_batch_sizes(duration)

                # If there's any unprocessed data, continue immediately.
                # Otherwise wait for new data.
                pending = self._count_pending_work()
                total_pending = sum(pending.values())

                if total_pending > 0:
                    breakdown = ", ".join(f"{stage}:{count}" for stage, count in pending.items())
                    logger.info(f"Found {total_pending} items pending ({breakdown})")
                    logger.info("Continuing immediately to process backlog...")
                    self._sleep_with_stop_check(BACKLOG_PAUSE_SECONDS)
                else:
                    logger.info(f"All articles fully processed, waiting {self.check_interval}s for new data...")
                    self._sleep_with_stop_check(self.check_interval)

            except KeyboardInterrupt:
                logger.info("Stopping continuous pipeline (keyboard interrupt)")
                self.running = False
                break
            except Exception as e:
                self.error_count += 1
                self.consecutive_errors += 1

                logger.error(f"Error in pipeline iteration #{iteration} (consecutive: {self.consecutive_errors}): {e}", exc_info=True)
                activity_logger.log_activity(f"Pipeline error: {str(e)}", "ERROR")

                # Close DB session if still open
                if self.db:
                    try:
                        self.db.close()
                    except Exception:
                        pass
                    finally:
                        self.db = None

                # Exponential backoff with max 5 minutes
                backoff_time = min(self.backoff_time * (2 ** (self.consecutive_errors - 1)), 300)
                logger.warning(f"Backing off for {backoff_time}s before retry (consecutive errors: {self.consecutive_errors})")

                # If too many consecutive errors, increase check interval temporarily
                if self.consecutive_errors >= 5:
                    logger.error(f"Too many consecutive errors ({self.consecutive_errors}), increasing backoff significantly")
                    backoff_time = 600  # 10 minutes

                self._sleep_with_stop_check(backoff_time)
            finally:
                # Ensure DB session is always closed
                if self.db:
                    try:
                        self.db.close()
                    except Exception:
                        pass
                    finally:
                        self.db = None

    @staticmethod
    def _count_pending_work() -> dict[str, int]:
        """Count rows still waiting at each pipeline stage.

        Drives the decision between looping straight into another iteration and
        sleeping until new articles arrive. Returns zeros if the check itself
        fails - a counting problem must not stall the pipeline.
        """
        from src.models.analysis import ImpactScore, SurpriseScore
        from src.models.entities import NewsEntityMapping
        from src.models.predictions import Prediction

        def missing_for(db, related_model):
            """ProcessedNews rows with no matching row in ``related_model``."""
            return db.query(ProcessedNews).outerjoin(
                related_model, ProcessedNews.news_id == related_model.news_id
            ).filter(related_model.news_id.is_(None)).count()

        try:
            with SessionLocal() as db:
                unassessed = db.query(RawNews).filter(
                    RawNews.quality_score.is_(None)
                ).count()

                # Quality-checked RawNews that has not been through NLP yet.
                unanalyzed = db.query(RawNews).filter(
                    RawNews.quality_score.is_not(None)
                ).outerjoin(
                    ProcessedNews, RawNews.news_id == ProcessedNews.news_id
                ).filter(ProcessedNews.news_id.is_(None)).count()

                # Predictions reference articles through a JSON array, so there
                # is no join to count them directly. Estimate instead: each
                # high-impact score should yield one prediction per horizon.
                high_impact = db.query(ImpactScore).filter(
                    ImpactScore.impact_score >= MIN_IMPACT_FOR_PREDICTION
                ).count()
                existing_predictions = db.query(Prediction).count()
                unpredicted = max(
                    0, high_impact * len(PREDICTION_HORIZONS) - existing_predictions
                )

                return {
                    'assessed': unassessed,
                    'analyzed': unanalyzed,
                    'mapped': missing_for(db, NewsEntityMapping),
                    'surprised': missing_for(db, SurpriseScore),
                    'scored': missing_for(db, ImpactScore),
                    'predicted': unpredicted,
                }
        except Exception as e:
            logger.error(f"Error checking pending work: {e}", exc_info=True)
            return {}

    def _phase_is_enabled(self, phase: PipelinePhase) -> bool:
        """Whether a settings-gated phase should run this iteration."""
        return phase.setting is None or bool(getattr(settings, phase.setting, False))

    def _auto_process_predictions(self):
        """Phase 10.5: turn fresh predictions into outcomes and simulations."""
        from src.services.auto_prediction_processor import auto_processor

        # Cover the predictions made since the previous iteration, plus slack.
        lookback_minutes = int(self.check_interval / 60) + 10
        stats = auto_processor.process_new_predictions(
            self.db, lookback_minutes=lookback_minutes
        )

        if stats['total_found'] > 0:
            logger.info(
                f"Auto-processed {stats['total_found']} predictions: "
                f"{stats['outcomes_created']} outcomes, "
                f"{stats['simulations_created']} simulations"
            )
        return stats

    def _run_phase(self, phase: PipelinePhase):
        """Run one phase and return its result (None if skipped or it failed softly)."""
        if not self._phase_is_enabled(phase):
            logger.debug(
                f"Phase {phase.number}: {phase.name} skipped "
                f"(disabled via {phase.setting})"
            )
            return None

        self._check_for_external_stop()
        activity_logger.log_phase(phase.number, phase.name)

        try:
            if phase.handler:
                result = getattr(self, phase.handler)()
            else:
                # build_agent passes self.db only to agents that still take one.
                agent = build_agent(phase.agent_class, self.db)
                kwargs = dict(phase.kwargs)
                if phase.batch_key:
                    kwargs['limit'] = self.batch_sizes[phase.batch_key]
                result = getattr(agent, phase.method)(**kwargs)
        except Exception as e:
            if not phase.optional:
                raise
            # An optional phase must not take the whole iteration down.
            logger.warning(f"Phase {phase.number} ({phase.name}) failed: {e}")
            return None

        # Handlers phrase their own result line; agent phases get the generic one.
        if not phase.handler:
            logger.info(f"{phase.name}: {result}")
        return result

    def _run_pipeline_iteration(self):
        """Run one complete pipeline iteration with dynamic batch sizes

        Returns:
            Number of new articles ingested

        NOTE: Agents now create their own scoped sessions for isolation.
        No shared session is passed to agents.
        """
        try:
            new_articles = 0

            for phase in PHASES:
                result = self._run_phase(phase)

                # Ingestion reports {feed: count}; the caller wants the total.
                if phase.method == 'fetch_all_rss_feeds' and result:
                    new_articles = sum(result.values())

            return new_articles

        except Exception as e:
            logger.error(f"Error in pipeline iteration: {e}", exc_info=True)
            raise

    def stop(self):
        """Stop the continuous pipeline gracefully"""
        logger.info("Stopping continuous pipeline...")
        activity_logger.log_activity("Continuous Pipeline STOPPED", "INFO")
        self.running = False

        # Close DB connection if still open
        if self.db:
            try:
                logger.info("Closing database connection...")
                self.db.close()
            except Exception as e:
                logger.error(f"Error closing DB on shutdown: {e}")
            finally:
                self.db = None

        # Log final statistics
        logger.info("Pipeline Statistics:")
        logger.info(f"  - Total Errors: {self.error_count}")
        logger.info(f"  - Avg Iteration Time: {self._get_avg_iteration_time():.1f}s")
        if self.iteration_times:
            logger.info(f"  - Min/Max Iteration: {min(self.iteration_times):.1f}s / {max(self.iteration_times):.1f}s")
        logger.info("Shutdown complete.")


def main():
    """Main entry point"""
    import argparse

    parser = argparse.ArgumentParser(
        description='Run TradeMeUp pipeline continuously with performance optimization',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Run with defaults (5min interval, 2GB memory limit)
  python run_continuous_pipeline.py
  
  # Check every 2 minutes with 4GB memory limit
  python run_continuous_pipeline.py --interval 120 --max-memory 4096
  
  # Aggressive mode (1min checks, 8GB memory)
  python run_continuous_pipeline.py --interval 60 --max-memory 8192
        """
    )
    parser.add_argument(
        '--interval',
        type=int,
        default=300,
        help='Seconds between pipeline runs (default: 300)'
    )
    parser.add_argument(
        '--max-memory',
        type=int,
        default=2048,
        help='Maximum memory usage in MB before forcing GC (default: 2048)'
    )

    args = parser.parse_args()

    pipeline = ContinuousPipeline(
        check_interval=args.interval,
        max_memory_mb=args.max_memory
    )

    try:
        pipeline.run()
    except KeyboardInterrupt:
        pipeline.stop()
        logger.info("Pipeline stopped by user")


if __name__ == "__main__":
    main()
