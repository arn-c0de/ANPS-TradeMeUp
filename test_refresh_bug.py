"""
Test to reproduce the refresh bug where performance shows 0.00%
"""

import logging
from sqlalchemy import create_engine
from sqlalchemy.orm import Session
from src.config.settings import settings
from src.services.prediction_performance_service import prediction_performance_service
from src.models.predictions import Prediction, PredictionOutcome
from src.models.entities import Entity

# Setup logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Create engine
engine = create_engine(settings.database_url)

def test_refresh_performance():
    """Test the refresh performance functionality"""
    
    # Get a recent prediction with Intel
    with Session(engine) as db:
        # Find Intel prediction
        prediction = db.query(Prediction).join(
            Entity, Prediction.entity_id == Entity.entity_id
        ).filter(
            Entity.entity_name.like('%Intel%')
        ).order_by(Prediction.created_at.desc()).first()
        
        if not prediction:
            logger.error("No GE Aerospace prediction found")
            return
        
        logger.info(f"Found prediction: {prediction.prediction_id}")
        logger.info(f"Entity: {prediction.entity_id}")
        logger.info(f"Created at: {prediction.created_at}")
        
        # Check current outcome
        existing_outcome = db.query(PredictionOutcome).filter(
            PredictionOutcome.prediction_id == prediction.prediction_id
        ).first()
        
        if existing_outcome:
            logger.info(f"Existing outcome: actual_return={existing_outcome.actual_return}")
        else:
            logger.info("No existing outcome found")
    
    # Now call the refresh function
    logger.info("\n" + "="*60)
    logger.info("CALLING calculate_and_save_performance")
    logger.info("="*60 + "\n")
    
    result = prediction_performance_service.calculate_and_save_performance(
        engine, 
        str(prediction.prediction_id)
    )
    
    logger.info("\n" + "="*60)
    logger.info(f"RESULT: {result}")
    logger.info("="*60 + "\n")
    
    # Check what was saved
    with Session(engine) as db:
        saved_outcome = db.query(PredictionOutcome).filter(
            PredictionOutcome.prediction_id == prediction.prediction_id
        ).first()
        
        if saved_outcome:
            logger.info(f"✅ Saved outcome found!")
            logger.info(f"   actual_return: {saved_outcome.actual_return}")
            logger.info(f"   direction_correct: {saved_outcome.direction_correct}")
            logger.info(f"   evaluation_timestamp: {saved_outcome.evaluation_timestamp}")
            
            if saved_outcome.actual_return == 0:
                logger.error("❌ BUG CONFIRMED: actual_return is 0!")
            else:
                logger.info(f"✅ actual_return looks correct: {saved_outcome.actual_return}%")
        else:
            logger.error("❌ No outcome saved!")

if __name__ == "__main__":
    test_refresh_performance()
