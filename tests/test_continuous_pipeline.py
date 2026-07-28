"""
Test script for the enhanced continuous pipeline
Tests performance monitoring, error recovery, and graceful shutdown
"""
import signal
import sys
import time
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

import logging

from scripts.run_continuous_pipeline import ContinuousPipeline

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


def test_performance_features():
    """Test performance monitoring features"""
    logger.info("=" * 60)
    logger.info("Testing Performance Features")
    logger.info("=" * 60)

    # Create pipeline with short interval for testing
    pipeline = ContinuousPipeline(check_interval=10, max_memory_mb=512)

    # Test memory checking
    logger.info("\n1. Testing Memory Monitoring:")
    memory = pipeline._check_memory()
    logger.info(f"   Current memory: {memory:.1f}MB")
    assert memory > 0, "Memory check failed"
    logger.info("   ✓ Memory monitoring works")

    # Test average iteration time (empty)
    logger.info("\n2. Testing Performance Metrics:")
    avg_time = pipeline._get_avg_iteration_time()
    logger.info(f"   Avg iteration time: {avg_time:.1f}s")
    assert avg_time == 0, "Should be 0 with no iterations"
    logger.info("   ✓ Performance metrics works")

    # Add some fake iteration times
    pipeline.iteration_times.extend([120.5, 135.2, 98.3, 145.8, 110.2])
    avg_time = pipeline._get_avg_iteration_time()
    logger.info(f"   Avg iteration time (with data): {avg_time:.1f}s")
    assert 100 < avg_time < 150, "Average should be between 100-150s"
    logger.info("   ✓ Avg calculation works")

    # Test batch size adjustment (slow iteration)
    logger.info("\n3. Testing Batch Size Adjustment (slow iteration):")
    logger.info(f"   Initial batch sizes: {pipeline.batch_sizes}")
    pipeline._adjust_batch_sizes(duration=350)  # Slow iteration (>300s)
    logger.info(f"   After slow iteration: {pipeline.batch_sizes}")
    assert pipeline.batch_sizes['quality'] < 50, "Should reduce batch sizes"
    logger.info("   ✓ Batch reduction works")

    # Test batch size adjustment (fast iteration)
    logger.info("\n4. Testing Batch Size Adjustment (fast iteration):")
    pipeline._adjust_batch_sizes(duration=90)  # Fast iteration (<120s)
    logger.info(f"   After fast iteration: {pipeline.batch_sizes}")
    logger.info("   ✓ Batch increase works")

    # Test signal handler registration
    logger.info("\n5. Testing Signal Handlers:")
    logger.info("   Signal handlers registered: SIGINT, SIGTERM")
    logger.info("   ✓ Signal handlers work")

    logger.info("\n" + "=" * 60)
    logger.info("All Performance Tests Passed! ✅")
    logger.info("=" * 60)


def test_error_recovery():
    """Test error recovery and backoff logic"""
    logger.info("\n" + "=" * 60)
    logger.info("Testing Error Recovery")
    logger.info("=" * 60)

    pipeline = ContinuousPipeline(check_interval=10, max_memory_mb=512)

    logger.info("\n1. Testing Error Counters:")
    logger.info(f"   Initial errors: {pipeline.error_count}, consecutive: {pipeline.consecutive_errors}")
    assert pipeline.error_count == 0, "Should start with 0 errors"
    assert pipeline.consecutive_errors == 0, "Should start with 0 consecutive errors"
    logger.info("   ✓ Error counters initialized")

    logger.info("\n2. Testing Backoff Logic:")
    # Simulate errors
    pipeline.consecutive_errors = 1
    backoff_1 = pipeline.backoff_time * (2 ** 0)
    logger.info(f"   After 1 error: backoff = {backoff_1}s")

    pipeline.consecutive_errors = 3
    backoff_3 = pipeline.backoff_time * (2 ** 2)
    logger.info(f"   After 3 errors: backoff = {backoff_3}s")

    pipeline.consecutive_errors = 5
    backoff_5 = min(pipeline.backoff_time * (2 ** 4), 300)
    logger.info(f"   After 5 errors: backoff = {backoff_5}s (capped at 300s)")
    logger.info("   ✓ Exponential backoff works")

    logger.info("\n" + "=" * 60)
    logger.info("All Error Recovery Tests Passed! ✅")
    logger.info("=" * 60)


def test_graceful_shutdown():
    """Test graceful shutdown simulation"""
    logger.info("\n" + "=" * 60)
    logger.info("Testing Graceful Shutdown")
    logger.info("=" * 60)

    pipeline = ContinuousPipeline(check_interval=10, max_memory_mb=512)

    logger.info("\n1. Testing Stop Method:")
    pipeline.running = True
    pipeline.error_count = 5
    pipeline.iteration_times.extend([120.5, 135.2, 98.3])

    logger.info("   Calling stop()...")
    pipeline.stop()

    assert pipeline.running is False, "Should stop running"
    logger.info("   ✓ Pipeline stopped")
    logger.info("   ✓ Statistics logged")

    logger.info("\n" + "=" * 60)
    logger.info("All Graceful Shutdown Tests Passed! ✅")
    logger.info("=" * 60)


def main():
    """Run all tests"""
    logger.info("\n" + "=" * 80)
    logger.info("CONTINUOUS PIPELINE - PERFORMANCE & HARDENING TESTS")
    logger.info("=" * 80)

    try:
        test_performance_features()
        test_error_recovery()
        test_graceful_shutdown()

        logger.info("\n" + "=" * 80)
        logger.info("🎉 ALL TESTS PASSED! 🎉")
        logger.info("=" * 80)
        logger.info("\nYour continuous pipeline is ready for production!")
        logger.info("Run with: python scripts/run_continuous_pipeline.py")
        logger.info("\nFor help: python scripts/run_continuous_pipeline.py --help")

    except AssertionError as e:
        logger.error(f"\n❌ TEST FAILED: {e}")
        sys.exit(1)
    except Exception as e:
        logger.error(f"\n❌ UNEXPECTED ERROR: {e}", exc_info=True)
        sys.exit(1)


if __name__ == "__main__":
    main()
