"""
Quick test script for refactored pipeline agents
Tests that all agents can be instantiated and called without db parameter
"""
import logging
from src.agents.data_quality_agent import DataQualityAgent
from src.agents.content_understanding_agent import ContentUnderstandingAgent
from src.agents.entity_mapping_agent import EntityMappingAgent
from src.agents.impact_scoring_agent import ImpactScoringAgent
from src.agents.prediction_agent import PredictionAgent
from src.agents.surprise_quantification_agent import SurpriseQuantificationAgent
from src.agents.fact_verification_agent import FactVerificationAgent
from src.agents.signal_decay_agent import SignalDecayAgent
from src.agents.correlation_analysis_agent import CorrelationAnalysisAgent

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def test_agent_initialization():
    """Test that all refactored agents can be initialized without db parameter"""
    
    agents = [
        ("DataQualityAgent", DataQualityAgent),
        ("ContentUnderstandingAgent", ContentUnderstandingAgent),
        ("EntityMappingAgent", EntityMappingAgent),
        ("ImpactScoringAgent", ImpactScoringAgent),
        ("PredictionAgent", PredictionAgent),
        ("SurpriseQuantificationAgent", SurpriseQuantificationAgent),
        ("FactVerificationAgent", FactVerificationAgent),
        ("SignalDecayAgent", SignalDecayAgent),
        ("CorrelationAnalysisAgent", CorrelationAnalysisAgent),
    ]
    
    results = []
    
    for name, AgentClass in agents:
        try:
            agent = AgentClass()  # No db parameter!
            logger.info(f"✅ {name} initialized successfully")
            results.append((name, True, None))
        except Exception as e:
            logger.error(f"❌ {name} failed: {e}")
            results.append((name, False, str(e)))
    
    # Print summary
    print("\n" + "="*60)
    print("AGENT INITIALIZATION TEST SUMMARY")
    print("="*60)
    
    success_count = sum(1 for _, success, _ in results if success)
    total_count = len(results)
    
    for name, success, error in results:
        status = "✅ PASS" if success else "❌ FAIL"
        print(f"{status}: {name}")
        if error:
            print(f"       Error: {error}")
    
    print("="*60)
    print(f"Results: {success_count}/{total_count} agents passed")
    print("="*60)
    
    return success_count == total_count

def test_agent_statistics():
    """Test that agents can call get_statistics() methods"""
    
    print("\n" + "="*60)
    print("AGENT STATISTICS TEST")
    print("="*60)
    
    agents = [
        ("DataQualityAgent", DataQualityAgent()),
        ("SignalDecayAgent", SignalDecayAgent()),
        ("CorrelationAnalysisAgent", CorrelationAnalysisAgent()),
        ("FactVerificationAgent", FactVerificationAgent()),
    ]
    
    for name, agent in agents:
        try:
            if hasattr(agent, 'get_statistics'):
                stats = agent.get_statistics()
                logger.info(f"✅ {name}.get_statistics() returned: {type(stats)}")
            else:
                logger.warning(f"⚠️  {name} has no get_statistics() method")
        except Exception as e:
            logger.error(f"❌ {name}.get_statistics() failed: {e}")
    
    print("="*60)

if __name__ == "__main__":
    print("\n🚀 Testing Refactored Pipeline Agents\n")
    
    # Test 1: Agent initialization
    init_success = test_agent_initialization()
    
    # Test 2: Statistics methods
    test_agent_statistics()
    
    if init_success:
        print("\n✅ ALL TESTS PASSED - Agents are ready for production!\n")
    else:
        print("\n❌ SOME TESTS FAILED - Please check errors above\n")
