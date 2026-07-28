"""
Test script to demonstrate live logging functionality
"""

import sys
import time
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

from src.utils.activity_logger import activity_logger


def test_live_logging():
    """Test the live logging functionality"""

    print("\n" + "=" * 70)
    print("🧪 TESTING LIVE LOGGING SYSTEM")
    print("=" * 70)
    print("\n📊 Open the dashboard at http://localhost:8050 to see live updates!\n")

    # Clear previous logs
    activity_logger.clear_logs()
    print("✅ Cleared old logs\n")

    time.sleep(2)

    # Simulate pipeline start
    activity_logger.log_pipeline_start("Test Pipeline")
    time.sleep(1)

    # Simulate Phase 1
    activity_logger.log_phase(1, "Data Collection")
    time.sleep(1)

    activity_logger.log_agent_start("Ingestion Agent", "1")
    time.sleep(1)

    # Simulate processing
    for i in range(1, 6):
        activity_logger.log_agent_processing("Ingestion Agent", f"Article {i}", i, 5)
        time.sleep(0.5)

    activity_logger.log_agent_success("Ingestion Agent", 5, 2.5)
    time.sleep(1)

    # Simulate Phase 2
    activity_logger.log_phase(2, "Quality Assessment")
    time.sleep(1)

    activity_logger.log_agent_start("Quality Agent", "2")
    time.sleep(1)

    for i in range(1, 4):
        activity_logger.log_agent_processing("Quality Agent", f"Article {i}", i, 3)
        time.sleep(0.5)

    activity_logger.log_agent_success("Quality Agent", 3, 1.5)
    time.sleep(1)

    # Simulate Phase 3 with LLM
    activity_logger.log_phase(3, "Content Understanding (LLM)")
    time.sleep(1)

    activity_logger.log_activity("Using LLM Provider: ollama (mistral)", "INFO")
    time.sleep(0.5)

    activity_logger.log_agent_start("Content Agent", "3")
    time.sleep(1)

    for i in range(1, 4):
        activity_logger.log_agent_processing("Content Agent", f"Analyzing Article {i}", i, 3)
        time.sleep(2)  # LLM is slower

    activity_logger.log_agent_success("Content Agent", 3, 6.0)
    time.sleep(1)

    # Simulate error in Phase 4
    activity_logger.log_phase(4, "Entity Mapping")
    time.sleep(1)

    activity_logger.log_agent_start("Entity Agent", "4")
    time.sleep(1)

    activity_logger.log_agent_processing("Entity Agent", "Article 1", 1, 2)
    time.sleep(0.5)

    activity_logger.log_agent_error("Entity Agent", "Connection timeout to external API")
    time.sleep(2)

    # Retry and succeed
    activity_logger.log_activity("Retrying with local extraction...", "INFO")
    time.sleep(1)

    activity_logger.log_agent_success("Entity Agent", 2, 1.2)
    time.sleep(1)

    # Pipeline complete
    activity_logger.log_pipeline_complete("Test Pipeline", 25.0)

    print("\n" + "=" * 70)
    print("✅ TEST COMPLETED!")
    print("=" * 70)
    print("\n📁 Log files created:")
    print("   - logs/pipeline_activity.log")
    print("   - logs/dashboard.log")
    print("\n💡 Check the dashboard to see live updates!")
    print("=" * 70 + "\n")


if __name__ == "__main__":
    test_live_logging()
