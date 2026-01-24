"""
Check ImpactScore and SurpriseScore tables - these are needed for predictions
"""

import logging
from sqlalchemy import create_engine, func
from sqlalchemy.orm import Session
from src.config.settings import settings
from src.models.analysis import ImpactScore, SurpriseScore
from src.models.entities import Entity

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

engine = create_engine(settings.database_url)

def check_analysis_tables():
    """Check why ImpactScore and SurpriseScore are missing"""
    
    with Session(engine) as db:
        # Count scores
        total_impact = db.query(func.count(ImpactScore.score_id)).scalar()
        total_surprise = db.query(func.count(SurpriseScore.surprise_id)).scalar()
        
        logger.info("="*70)
        logger.info("📊 ANALYSIS SCORES")
        logger.info("="*70)
        logger.info(f"Total ImpactScores: {total_impact}")
        logger.info(f"Total SurpriseScores: {total_surprise}")
        logger.info("")
        
        # Show some impact scores
        if total_impact > 0:
            logger.info("Sample ImpactScores:")
            samples = db.query(ImpactScore).limit(10).all()
            for s in samples:
                entity = db.query(Entity).filter(Entity.entity_id == s.entity_id).first()
                logger.info(f"  News: {s.news_id}, Entity: {s.entity_id} ({entity.entity_name if entity else 'Unknown'}), Score: {s.impact_score}")
        
        # Show surprise scores  
        if total_surprise > 0:
            logger.info("\nSample SurpriseScores:")
            samples = db.query(SurpriseScore).limit(10).all()
            for s in samples:
                logger.info(f"  News: {s.news_id}, Metric: {s.metric}, Surprise: {s.surprise_normalized}, Expected: {s.expected_reaction}")
        
        logger.info("\n" + "="*70)
        logger.info("🔍 DIAGNOSIS")
        logger.info("="*70)
        logger.info(f"✅ Processed News exist: 2074")
        logger.info(f"❌ ImpactScores missing: Need {2074 - total_impact} more")
        logger.info(f"❌ SurpriseScores missing: Need {2074 - total_surprise} more")
        logger.info("")
        logger.info("📌 ROOT CAUSE: The pipeline is NOT creating ImpactScore/SurpriseScore entries!")
        logger.info("   These are required for generating predictions.")
        logger.info("")
        logger.info("💡 SOLUTION: Check the pipeline that should create these scores:")
        logger.info("   1. src/agents/impact_analysis_agent.py")
        logger.info("   2. src/agents/surprise_evaluation_agent.py")
        logger.info("   3. Pipeline orchestration in scripts/")

if __name__ == "__main__":
    check_analysis_tables()
