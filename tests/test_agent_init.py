"""Test agents with empty database (proper initialization test)."""
import os
import sys

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

import logging

from src.agents.ab_testing_agent import ABTestingAgent
from src.agents.confidence_calibration_agent import ConfidenceCalibrationAgent
from src.agents.content_understanding_agent import ContentUnderstandingAgent
from src.agents.correlation_analysis_agent import CorrelationAnalysisAgent
from src.agents.data_quality_agent import DataQualityAgent
from src.agents.entity_mapping_agent import EntityMappingAgent
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
from src.models.database import get_db

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)

logger = logging.getLogger(__name__)


def _test_agent_init(agent_class, agent_name, db):
    """Test if agent can be initialized successfully."""
    logger.info(f"\n{'='*80}")
    logger.info(f"Testing Initialization: {agent_name}")
    logger.info(f"{'='*80}")

    try:
        # Just try to initialize agent
        agent = agent_class(db)
        logger.info(f"✅ {agent_name} - Successfully initialized")

        # Try to get statistics (this may return empty results but shouldn't crash)
        try:
            if hasattr(agent, 'get_statistics'):
                stats = agent.get_statistics()
                logger.info(f"   Statistics: {stats}")
        except Exception as e:
            logger.warning(f"   Statistics error (expected for empty DB): {type(e).__name__}")

        return True

    except Exception as e:
        logger.error(f"❌ {agent_name} - Initialization Error: {e}")
        import traceback
        traceback.print_exc()
        return False


def run_init_tests():
    """Run initialization tests for all agents."""
    logger.info("="*80)
    logger.info("TradeMeUp Agent Initialization Test Suite")
    logger.info("="*80)

    db = next(get_db())

    # Define all agents to test
    agents = [
        # TIER 1: Data Ingestion
        (IngestionAgent, "Agent 1: Ingestion Agent"),
        (DataQualityAgent, "Agent 1.5: Data Quality Agent"),

        # TIER 2: Understanding
        (ContentUnderstandingAgent, "Agent 2: Content Understanding Agent"),
        (FactVerificationAgent, "Agent 2.5: Fact Verification Agent"),
        (EntityMappingAgent, "Agent 3: Entity Mapping Agent"),

        # TIER 3: Analysis
        (ImpactScoringAgent, "Agent 4: Impact Scoring Agent"),
        (SurpriseQuantificationAgent, "Agent 4.5: Surprise Quantification Agent"),
        (RegimeDetectionAgent, "Agent 5: Regime Detection Agent"),
        (SignalDecayAgent, "Agent 5.5: Signal Decay Agent"),
        (CorrelationAnalysisAgent, "Agent 5.6: Correlation Analysis Agent"),

        # TIER 4: Prediction
        (PredictionAgent, "Agent 6: Prediction Agent"),
        (ConfidenceCalibrationAgent, "Agent 6.5: Confidence Calibration Agent"),
        (MetaStrategyAgent, "Agent 7: Meta-Strategy Agent"),
        (ScenarioGenerationAgent, "Agent 7.5: Scenario Generation Agent"),

        # TIER 6: Learning & Monitoring
        (ModelPerformanceMonitor, "Agent 12.5: Model Performance Monitor"),
        (ABTestingAgent, "Agent 13: A/B Testing Framework"),
    ]

    passed = 0
    failed = 0

    for agent_class, agent_name in agents:
        success = _test_agent_init(agent_class, agent_name, db)
        if success:
            passed += 1
        else:
            failed += 1

    # Summary
    logger.info(f"\n{'='*80}")
    logger.info("INITIALIZATION TEST SUMMARY")
    logger.info(f"{'='*80}")
    logger.info(f"Total Agents Tested: {len(agents)}")
    logger.info(f"✅ Successfully Initialized: {passed}")
    logger.info(f"❌ Initialization Failed: {failed}")
    logger.info(f"Success Rate: {passed/len(agents)*100:.1f}%")

    if passed == len(agents):
        logger.info("\n🎉 ALL AGENTS INITIALIZED SUCCESSFULLY!")
        logger.info("Note: Empty database is expected. Run the pipeline to populate data.")

    return passed == len(agents)


if __name__ == "__main__":
    success = run_init_tests()
    exit(0 if success else 1)
