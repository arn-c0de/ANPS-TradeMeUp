"""Test new agents specifically (2.5, 5.5, 5.6, 6.5, 7, 7.5, 12.5, 13)."""
import sys
sys.path.insert(0, '.')

import logging
from src.models.database import get_db
from src.agents.fact_verification_agent import FactVerificationAgent
from src.agents.signal_decay_agent import SignalDecayAgent
from src.agents.correlation_analysis_agent import CorrelationAnalysisAgent
from src.agents.confidence_calibration_agent import ConfidenceCalibrationAgent
from src.agents.meta_strategy_agent import MetaStrategyAgent
from src.agents.scenario_generation_agent import ScenarioGenerationAgent
from src.agents.model_performance_monitor import ModelPerformanceMonitor
from src.agents.ab_testing_agent import ABTestingAgent

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)

logger = logging.getLogger(__name__)


def test_fact_verification():
    """Test Fact Verification Agent."""
    logger.info("\n" + "="*80)
    logger.info("Testing Agent 2.5: Fact Verification Agent")
    logger.info("="*80)

    db = next(get_db())
    agent = FactVerificationAgent(db)

    # Test statistics
    stats = agent.get_statistics()
    logger.info(f"Statistics: {stats}")

    # Test batch processing (small batch)
    logger.info("\nRunning batch verification (limit=3)...")
    batch_stats = agent.process_batch(limit=3)
    logger.info(f"Batch results: {batch_stats}")

    return stats


def test_signal_decay():
    """Test Signal Decay Agent."""
    logger.info("\n" + "="*80)
    logger.info("Testing Agent 5.5: Signal Decay Agent")
    logger.info("="*80)

    db = next(get_db())
    agent = SignalDecayAgent(db)

    # Test statistics
    stats = agent.get_statistics()
    logger.info(f"Statistics: {stats}")

    # Test decay calculation
    logger.info("\nTesting decay calculation...")
    decayed_impact = agent.calculate_decay(
        initial_impact=0.8,
        time_elapsed_hours=24,
        event_type='earnings'
    )
    logger.info(f"Decayed impact after 24h: {decayed_impact:.4f} (initial: 0.8)")

    return stats


def test_correlation_analysis():
    """Test Correlation Analysis Agent."""
    logger.info("\n" + "="*80)
    logger.info("Testing Agent 5.6: Correlation Analysis Agent")
    logger.info("="*80)

    db = next(get_db())
    agent = CorrelationAnalysisAgent(db)

    # Test statistics
    stats = agent.get_statistics()
    logger.info(f"Statistics: {stats}")

    return stats


def test_confidence_calibration():
    """Test Confidence Calibration Agent."""
    logger.info("\n" + "="*80)
    logger.info("Testing Agent 6.5: Confidence Calibration Agent")
    logger.info("="*80)

    agent = ConfidenceCalibrationAgent()

    # Test statistics
    stats = agent.get_statistics()
    logger.info(f"Statistics: {stats}")

    # Test confidence calibration
    logger.info("\nTesting confidence calibration...")
    raw_conf = 0.85
    calibrated = agent.calibrate_confidence(raw_conf)
    logger.info(f"Raw confidence: {raw_conf:.2f} -> Calibrated: {calibrated:.2f}")

    return stats


def test_meta_strategy():
    """Test Meta-Strategy Agent."""
    logger.info("\n" + "="*80)
    logger.info("Testing Agent 7: Meta-Strategy Agent")
    logger.info("="*80)

    agent = MetaStrategyAgent()

    # Test statistics
    stats = agent.get_statistics()
    logger.info(f"Statistics: {stats}")

    # Calculate model weights
    logger.info("\nCalculating model weights...")
    weights = agent.calculate_model_weights(lookback_days=30)
    logger.info(f"Model weights: {weights}")

    return stats


def test_scenario_generation():
    """Test Scenario Generation Agent."""
    logger.info("\n" + "="*80)
    logger.info("Testing Agent 7.5: Scenario Generation Agent")
    logger.info("="*80)

    db = next(get_db())
    agent = ScenarioGenerationAgent(db)

    # Test statistics
    stats = agent.get_statistics()
    logger.info(f"Statistics: {stats}")

    # Generate scenarios
    logger.info("\nGenerating scenarios...")
    batch_stats = agent.process_batch(limit=3)
    logger.info(f"Generated {batch_stats['scenarios_generated']} scenarios")

    # Test stress testing
    logger.info("\nStress testing a prediction...")
    stress_result = agent.stress_test_prediction(
        base_prediction=0.05,
        scenario_type='market_crash'
    )
    logger.info(f"Stress test result: {stress_result}")

    return stats


def test_model_performance_monitor():
    """Test Model Performance Monitor."""
    logger.info("\n" + "="*80)
    logger.info("Testing Agent 12.5: Model Performance Monitor")
    logger.info("="*80)

    db = next(get_db())
    agent = ModelPerformanceMonitor(db)

    # Test statistics
    stats = agent.get_statistics()
    logger.info(f"Statistics: {stats}")

    return stats


def test_ab_testing():
    """Test A/B Testing Agent."""
    logger.info("\n" + "="*80)
    logger.info("Testing Agent 13: A/B Testing Framework")
    logger.info("="*80)

    db = next(get_db())
    agent = ABTestingAgent(db)

    # Test statistics
    stats = agent.get_statistics()
    logger.info(f"Statistics: {stats}")

    # Create a test
    logger.info("\nCreating A/B test...")
    test_config = agent.create_ab_test(
        test_name="baseline_vs_ensemble",
        model_a="xgboost_baseline",
        model_b="meta_ensemble",
        traffic_split=0.5,
        duration_days=30
    )
    logger.info(f"Test created: {test_config['test_id']}")

    return stats


def run_all_new_agent_tests():
    """Run all new agent tests."""
    logger.info("="*80)
    logger.info("TradeMeUp New Agents Test Suite")
    logger.info("Testing 8 newly implemented agents")
    logger.info("="*80)

    tests = [
        ("Agent 2.5: Fact Verification", test_fact_verification),
        ("Agent 5.5: Signal Decay", test_signal_decay),
        ("Agent 5.6: Correlation Analysis", test_correlation_analysis),
        ("Agent 6.5: Confidence Calibration", test_confidence_calibration),
        ("Agent 7: Meta-Strategy", test_meta_strategy),
        ("Agent 7.5: Scenario Generation", test_scenario_generation),
        ("Agent 12.5: Model Performance Monitor", test_model_performance_monitor),
        ("Agent 13: A/B Testing", test_ab_testing),
    ]

    results = {}
    passed = 0
    failed = 0

    for test_name, test_func in tests:
        try:
            logger.info(f"\nRunning: {test_name}...")
            result = test_func()
            results[test_name] = {'success': True, 'result': result}
            passed += 1
            logger.info(f"✅ {test_name} - PASSED")
        except Exception as e:
            results[test_name] = {'success': False, 'error': str(e)}
            failed += 1
            logger.error(f"❌ {test_name} - FAILED: {e}")
            import traceback
            traceback.print_exc()

    # Summary
    logger.info(f"\n{'='*80}")
    logger.info("TEST SUMMARY")
    logger.info(f"{'='*80}")
    logger.info(f"Total Tests: {len(tests)}")
    logger.info(f"✅ Passed: {passed}")
    logger.info(f"❌ Failed: {failed}")
    logger.info(f"Success Rate: {passed/len(tests)*100:.1f}%")

    return results


if __name__ == "__main__":
    results = run_all_new_agent_tests()
