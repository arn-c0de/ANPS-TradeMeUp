"""Comprehensive test script for all agents."""
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


def _test_agent(agent_class, agent_name, db, test_method='get_statistics'):
    """Test a single agent."""
    logger.info(f"\n{'='*80}")
    logger.info(f"Testing {agent_name}")
    logger.info(f"{'='*80}")

    try:
        agent = agent_class(db)

        # Get statistics
        if hasattr(agent, test_method):
            stats = getattr(agent, test_method)()
            logger.info(f"✅ {agent_name} - Statistics:")
            for key, value in stats.items():
                logger.info(f"   {key}: {value}")
            return True, stats
        else:
            logger.warning(f"⚠️  {agent_name} - No {test_method} method")
            return False, {}

    except Exception as e:
        logger.error(f"❌ {agent_name} - Error: {e}")
        import traceback
        traceback.print_exc()
        return False, {}


def run_all_tests():
    """Run tests for all agents."""
    logger.info("="*80)
    logger.info("TradeMeUp Agent Test Suite")
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

    results = {}
    passed = 0
    failed = 0

    for agent_class, agent_name in agents:
        success, stats = _test_agent(agent_class, agent_name, db)
        results[agent_name] = {'success': success, 'stats': stats}

        if success:
            passed += 1
        else:
            failed += 1

    # Summary
    logger.info(f"\n{'='*80}")
    logger.info("TEST SUMMARY")
    logger.info(f"{'='*80}")
    logger.info(f"Total Agents Tested: {len(agents)}")
    logger.info(f"✅ Passed: {passed}")
    logger.info(f"❌ Failed: {failed}")
    logger.info(f"Success Rate: {passed/len(agents)*100:.1f}%")

    return results


if __name__ == "__main__":
    results = run_all_tests()
