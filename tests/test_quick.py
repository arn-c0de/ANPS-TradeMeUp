"""Quick MVP Test - Only 1 article per agent."""
import sys
from pathlib import Path

project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

from src.models.database import SessionLocal
from src.agents.ingestion_agent import IngestionAgent
from src.agents.data_quality_agent import DataQualityAgent
from src.agents.content_understanding_agent import ContentUnderstandingAgent
from src.agents.entity_mapping_agent import EntityMappingAgent
from src.agents.surprise_quantification_agent import SurpriseQuantificationAgent
from src.agents.regime_detection_agent import RegimeDetectionAgent
from src.agents.impact_scoring_agent import ImpactScoringAgent
from src.agents.prediction_agent import PredictionAgent
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def main():
    db = SessionLocal()
    try:
        logger.info("✅ Testing MVP Agents (Quick Version)")
        
        # Agent 1: Ingestion
        logger.info("\n1️⃣ Agent 1: Ingestion")
        ing = IngestionAgent(db)
        stats = ing.get_statistics()
        logger.info(f"   Articles in DB: {stats['total_articles']}")
        
        # Agent 1.5: Quality (only 1 article)
        logger.info("\n2️⃣ Agent 1.5: Quality")
        quality = DataQualityAgent(db)
        result = quality.process_batch(limit=1)
        logger.info(f"   Processed: {result}")
        
        # Agent 2: Content Understanding (only 1 article)
        logger.info("\n3️⃣ Agent 2: Content Understanding")
        content = ContentUnderstandingAgent(db)
        result = content.process_batch(limit=1)
        logger.info(f"   Processed: {result}")
        
        # Agent 3: Entity Mapping
        logger.info("\n4️⃣ Agent 3: Entity Mapping")
        entities = EntityMappingAgent(db)
        result = entities.process_batch(limit=1)
        logger.info(f"   Processed: {result}")
        
        # Agent 5: Regime Detection
        logger.info("\n5️⃣ Agent 5: Market Regime")
        regime = RegimeDetectionAgent(db)
        current = regime.update_regime()
        logger.info(f"   Regime: {current.regime}")
        
        # Agent 4.5: Surprise Quantification
        logger.info("\n6️⃣ Agent 4.5: Surprise Quantification")
        surprise = SurpriseQuantificationAgent(db)
        result = surprise.process_batch(limit=1)
        logger.info(f"   Processed: {result}")
        
        # Agent 4: Impact Scoring
        logger.info("\n7️⃣ Agent 4: Impact Scoring")
        impact = ImpactScoringAgent(db)
        result = impact.process_batch(limit=1)
        logger.info(f"   Processed: {result}")
        
        # Agent 6: Predictions
        logger.info("\n8️⃣ Agent 6: Predictions")
        predictor = PredictionAgent(db)
        result = predictor.process_batch(limit=1)
        logger.info(f"   Processed: {result}")
        
        logger.info("\n✅ ALL AGENTS WORKING!")
        
    except Exception as e:
        logger.error(f"❌ Error: {e}", exc_info=True)
    finally:
        db.close()

if __name__ == "__main__":
    main()
