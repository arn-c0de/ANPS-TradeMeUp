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
import sys
import time
import signal
import logging
import psutil
from pathlib import Path
from datetime import datetime, timezone
from typing import Optional
from collections import deque

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from src.models.database import SessionLocal
from src.models.raw_news import RawNews
from src.models.processed_news import ProcessedNews
from src.models.system_logs import SystemLog
from src.agents.ingestion_agent import IngestionAgent
from src.agents.data_quality_agent import DataQualityAgent
from src.agents.content_understanding_agent import ContentUnderstandingAgent
from src.agents.entity_mapping_agent import EntityMappingAgent
from src.agents.surprise_quantification_agent import SurpriseQuantificationAgent
from src.agents.regime_detection_agent import RegimeDetectionAgent
from src.agents.impact_scoring_agent import ImpactScoringAgent
from src.agents.prediction_agent import PredictionAgent
from src.agents.trading_simulation_agent import TradingSimulationAgent
# NEW AGENTS from Phase 2
from src.agents.fact_verification_agent import FactVerificationAgent
from src.agents.signal_decay_agent import SignalDecayAgent
from src.agents.correlation_analysis_agent import CorrelationAnalysisAgent
from src.agents.confidence_calibration_agent import ConfidenceCalibrationAgent
from src.agents.meta_strategy_agent import MetaStrategyAgent
from src.agents.scenario_generation_agent import ScenarioGenerationAgent
from src.agents.model_performance_monitor import ModelPerformanceMonitor
from src.agents.ab_testing_agent import ABTestingAgent
from src.config.settings import settings
from src.utils.activity_logger import activity_logger

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

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
        self.db: Optional[object] = None
        self.started_at_utc: Optional[datetime] = None
        
        # Performance metrics
        self.iteration_times = deque(maxlen=20)  # Last 20 iteration times
        self.error_count = 0
        self.consecutive_errors = 0
        self.backoff_time = 5  # Initial backoff time in seconds
        
        # Dynamic batch sizes (will be adjusted based on performance)
        self.batch_sizes = {
            'quality': 50,
            'content': 30,  # Increased from 10 to 30
            'entity': 20,   # Increased from 10 to 20
            'surprise': 30,  # Increased from 20 to 30
            'impact': 30,    # Increased from 20 to 30
            'prediction': 50,
            'simulation': 50,
            # NEW AGENTS
            'fact_verification': 30,
            'correlation': 10,  # Lower because it's computation-heavy
            'calibration': 20,
            'meta_strategy': 10  # Creates ensemble predictions
        }
        
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
        
        phases = [
            ("Phase 12: Scenario Generation", settings.enable_scenarios),
            ("Phase 13: Fact Verification", settings.enable_fact_checking),
            ("Phase 14: Confidence Calibration", settings.enable_calibration),
            ("Phase 15: Meta-Strategy Ensemble", settings.enable_meta_strategy),
        ]
        
        enabled_phases = []
        disabled_phases = []
        
        for phase_name, is_enabled in phases:
            if is_enabled:
                enabled_phases.append(phase_name)
            else:
                disabled_phases.append(phase_name)
        
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
        # If iteration took too long (>5 min), reduce batch sizes
        if duration > 300:
            for key in self.batch_sizes:
                self.batch_sizes[key] = max(5, int(self.batch_sizes[key] * 0.8))
            logger.info(f"Reduced batch sizes due to slow iteration: {self.batch_sizes}")
        # If iteration was fast (<2 min) and no recent errors, increase batch sizes
        elif duration < 120 and self.consecutive_errors == 0:
            for key in self.batch_sizes:
                max_size = {
                    'quality': 100,
                    'content': 50,  # Increased max
                    'entity': 30,   # Increased max
                    'surprise': 50,
                    'impact': 50,
                    'prediction': 100,
                    'simulation': 100,
                    'fact_verification': 50,
                    'correlation': 20,
                    'calibration': 30,
                    'meta_strategy': 20
                }
                self.batch_sizes[key] = min(max_size.get(key, 50), int(self.batch_sizes[key] * 1.2))
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
        self.started_at_utc = datetime.now(timezone.utc)
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
                
                # Check if there's any unprocessed work in the pipeline
                check_db = SessionLocal()
                try:
                    from src.models.analysis import SurpriseScore, ImpactScore
                    from src.models.predictions import Prediction
                    from src.models.entities import NewsEntityMapping
                    from sqlalchemy import and_
                    
                    # Count articles at different pipeline stages that need processing
                    # 1. RawNews without quality_score (use == None for SQLAlchemy)
                    unassessed = check_db.query(RawNews).filter(RawNews.quality_score == None).count()
                    
                    # 2. Quality-checked RawNews without ProcessedNews
                    unanalyzed = check_db.query(RawNews).filter(
                        RawNews.quality_score != None
                    ).outerjoin(
                        ProcessedNews, RawNews.news_id == ProcessedNews.news_id
                    ).filter(ProcessedNews.news_id == None).count()
                    
                    # 3. ProcessedNews without entity mapping
                    unmapped = check_db.query(ProcessedNews).outerjoin(
                        NewsEntityMapping, ProcessedNews.news_id == NewsEntityMapping.news_id
                    ).filter(NewsEntityMapping.news_id == None).count()
                    
                    # 4. ProcessedNews without surprise score
                    unsurprised = check_db.query(ProcessedNews).outerjoin(
                        SurpriseScore, ProcessedNews.news_id == SurpriseScore.news_id
                    ).filter(SurpriseScore.news_id == None).count()
                    
                    # 5. ProcessedNews without impact score
                    unscored = check_db.query(ProcessedNews).outerjoin(
                        ImpactScore, ProcessedNews.news_id == ImpactScore.news_id
                    ).filter(ImpactScore.news_id == None).count()
                    
                    # 6. ImpactScores >= 0.4 without predictions (simplified check)
                    # Note: Predictions use related_news_ids JSON array, so we check ImpactScores instead
                    high_impact_scores = check_db.query(ImpactScore).filter(
                        ImpactScore.impact_score >= 0.4
                    ).count()

                    existing_predictions = check_db.query(Prediction).count()

                    # Rough estimate: each high impact should have 3 predictions (1d, 5d, 20d)
                    expected_predictions = high_impact_scores * 3
                    unpredicted = max(0, expected_predictions - existing_predictions)

                    total_pending = unassessed + unanalyzed + unmapped + unsurprised + unscored + unpredicted
                except Exception as e:
                    logger.error(f"Error checking pending work: {e}", exc_info=True)
                    total_pending = 0  # Continue anyway if check fails
                finally:
                    check_db.close()
                
                # If there's any unprocessed data, continue immediately
                # Otherwise wait for new data
                if total_pending > 0:
                    logger.info(f"Found {total_pending} items pending (assessed:{unassessed}, analyzed:{unanalyzed}, mapped:{unmapped}, surprised:{unsurprised}, scored:{unscored}, predicted:{unpredicted})")
                    logger.info("Continuing immediately to process backlog...")
                    self._sleep_with_stop_check(2)  # Brief pause to avoid overwhelming the system
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
                    except:
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
                    except:
                        pass
                    finally:
                        self.db = None
    
    def _run_pipeline_iteration(self):
        """Run one complete pipeline iteration with dynamic batch sizes

        Returns:
            Number of new articles ingested

        NOTE: Agents now create their own scoped sessions for isolation.
        No shared session is passed to agents.
        """
        try:
            # Phase 1: Data Ingestion
            self._check_for_external_stop()
            activity_logger.log_phase(1, "Data Ingestion")
            ingestion = IngestionAgent(self.db)
            rss_results = ingestion.fetch_all_rss_feeds()
            new_articles = sum(rss_results.values())
            logger.info(f"Ingested: {rss_results}")

            # Phase 2: Quality Check (process unassessed articles) - DYNAMIC BATCH SIZE
            # ✅ REFACTORED: Uses scoped sessions internally
            self._check_for_external_stop()
            activity_logger.log_phase(2, "Quality Assessment")
            quality = DataQualityAgent()  # ✅ No db parameter!
            quality_results = quality.process_batch(limit=self.batch_sizes['quality'])
            logger.info(f"Quality check: {quality_results}")

            # Phase 3: Content Understanding - ✅ OPTIMIZED with scoped sessions
            self._check_for_external_stop()
            activity_logger.log_phase(3, "Content Analysis")
            content = ContentUnderstandingAgent()  # ✅ No db parameter!
            content_results = content.process_batch(limit=self.batch_sizes['content'])
            logger.info(f"NLP Analysis: {content_results}")
            
            # Phase 4: Entity Mapping - ✅ OPTIMIZED with scoped sessions
            self._check_for_external_stop()
            activity_logger.log_phase(4, "Entity Mapping")
            entities = EntityMappingAgent()  # ✅ No db parameter!
            entity_results = entities.process_batch(limit=self.batch_sizes['entity'])
            logger.info(f"Entities: {entity_results}")

            # Phase 5: Market Regime (single update, no batch)
            # TODO: Refactor RegimeDetectionAgent to use scoped sessions
            self._check_for_external_stop()
            activity_logger.log_phase(5, "Market Regime")
            regime = RegimeDetectionAgent(self.db)
            regime_result = regime.update_regime()
            logger.info(f"Regime: {regime_result}")

            # Phase 6: Surprise Quantification - DYNAMIC BATCH SIZE
            # ✅ REFACTORED: Uses scoped sessions internally
            self._check_for_external_stop()
            activity_logger.log_phase(6, "Surprise Quantification")
            surprise = SurpriseQuantificationAgent()  # ✅ No db parameter!
            surprise_results = surprise.process_batch(limit=self.batch_sizes['surprise'])
            logger.info(f"Surprises: {surprise_results}")

            # Phase 7: Impact Scoring - ✅ OPTIMIZED with scoped sessions
            self._check_for_external_stop()
            activity_logger.log_phase(7, "Impact Scoring")
            impact = ImpactScoringAgent()  # ✅ No db parameter!
            impact_results = impact.process_batch(limit=self.batch_sizes['impact'])
            logger.info(f"Impact: {impact_results}")

            # Phase 8: Signal Decay Modeling (apply to impact scores)
            # ✅ REFACTORED: Uses scoped sessions internally
            self._check_for_external_stop()
            activity_logger.log_phase(8, "Signal Decay Modeling")
            signal_decay = SignalDecayAgent()  # ✅ No db parameter!
            decay_stats = signal_decay.get_statistics()
            logger.info(f"Signal Decay: {decay_stats}")

            # Phase 9: Correlation Analysis (between entities)
            # ✅ REFACTORED: Uses scoped sessions internally
            self._check_for_external_stop()
            activity_logger.log_phase(9, "Correlation Analysis")
            correlation = CorrelationAnalysisAgent()  # ✅ No db parameter!
            corr_stats = correlation.get_statistics()
            logger.info(f"Correlation: {corr_stats}")
            
            # Phase 10: Predictions - ✅ OPTIMIZED with scoped sessions
            self._check_for_external_stop()
            activity_logger.log_phase(10, "Predictions")
            predictions = PredictionAgent()  # ✅ No db parameter!
            pred_results = predictions.process_batch(limit=self.batch_sizes['prediction'])
            logger.info(f"Predictions: {pred_results}")

            # Phase 10.5: Auto-Process New Predictions (Performance & Simulations)
            self._check_for_external_stop()
            activity_logger.log_phase(10.5, "Auto-Processing Predictions")
            try:
                from src.services.auto_prediction_processor import auto_processor
                # Process predictions from last iteration (check_interval + buffer)
                lookback_minutes = int(self.check_interval / 60) + 10
                auto_stats = auto_processor.process_new_predictions(self.db, lookback_minutes=lookback_minutes)
                
                if auto_stats['total_found'] > 0:
                    logger.info(f"Auto-processed {auto_stats['total_found']} predictions: "
                              f"{auto_stats['outcomes_created']} outcomes, "
                              f"{auto_stats['simulations_created']} simulations")
            except Exception as e:
                logger.warning(f"Auto-processing failed: {e}")
                # Continue pipeline even if auto-processing fails

            # ===== NEW PHASES (Phase 2 Agents) =====

            # Phase 11: Trading Simulation (predictions vs market)
            self._check_for_external_stop()
            activity_logger.log_phase(11, "Trading Simulation")
            simulator = TradingSimulationAgent()
            sim_results = simulator.process_batch(limit=self.batch_sizes['simulation'], lookback_days=7)
            logger.info(f"Simulation: {sim_results}")

            # Phase 12: Scenario Generation (stress test predictions)
            # Check if scenarios are enabled in settings
            if settings.enable_scenarios:
                self._check_for_external_stop()
                activity_logger.log_phase(12, "Scenario Generation")
                scenario_gen = ScenarioGenerationAgent(self.db)
                scenario_stats = scenario_gen.get_statistics()
                logger.info(f"Scenarios: {scenario_stats}")
            else:
                logger.debug("Phase 12: Scenario Generation skipped (disabled in settings)")

            # Phase 13: Fact Verification
            # ✅ REFACTORED: Uses scoped sessions internally
            # Check if fact checking is enabled in settings (can be expensive in tokens)
            if settings.enable_fact_checking:
                self._check_for_external_stop()
                activity_logger.log_phase(13, "Fact Verification")
                fact_verifier = FactVerificationAgent()  # ✅ No db parameter!
                fact_results = fact_verifier.process_batch(limit=self.batch_sizes['fact_verification'])
                logger.info(f"Fact Verification: {fact_results}")
            else:
                logger.debug("Phase 13: Fact Verification skipped (disabled in settings to save tokens)")

            # Phase 14: Confidence Calibration (for predictions)
            # ✅ REFACTORED: Uses scoped sessions internally
            # Check if calibration is enabled in settings
            if settings.enable_calibration:
                self._check_for_external_stop()
                activity_logger.log_phase(14, "Confidence Calibration")
                calibrator = ConfidenceCalibrationAgent()  # ✅ No db parameter!
                calibration_stats = calibrator.get_statistics()
                logger.info(f"Calibration: {calibration_stats}")
            else:
                logger.debug("Phase 14: Confidence Calibration skipped (disabled in settings)")

            # Phase 15: Meta-Strategy (Ensemble Predictions)
            # ✅ REFACTORED: Uses scoped sessions internally
            # Check if meta-strategy is enabled in settings
            if settings.enable_meta_strategy:
                self._check_for_external_stop()
                activity_logger.log_phase(15, "Meta-Strategy Ensemble")
                meta_strategy = MetaStrategyAgent()  # ✅ No db parameter!
                # Get entities that have multiple predictions for ensemble
                ensemble_results = meta_strategy.get_statistics()
                logger.info(f"Meta-Strategy: {ensemble_results}")
            else:
                logger.debug("Phase 15: Meta-Strategy Ensemble skipped (disabled in settings)")

            # Phase 16: Model Performance Monitoring
            # TODO: Refactor when needed
            self._check_for_external_stop()
            activity_logger.log_phase(16, "Performance Monitoring")
            monitor = ModelPerformanceMonitor(self.db)
            perf_stats = monitor.get_statistics()
            logger.info(f"Performance: {perf_stats}")

            # Phase 17: A/B Testing (compare model versions)
            # TODO: Refactor when needed
            self._check_for_external_stop()
            activity_logger.log_phase(17, "A/B Testing")
            ab_testing = ABTestingAgent(self.db)
            ab_stats = ab_testing.get_statistics()
            logger.info(f"A/B Testing: {ab_stats}")

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
