"""
Test the NEW refresh logic that uses Details view calculation
"""

import logging
from sqlalchemy import create_engine
from sqlalchemy.orm import Session
from src.config.settings import settings
from src.models.predictions import Prediction, PredictionOutcome
from src.models.entities import Entity

# Setup logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Create engine
engine = create_engine(settings.database_url)

def test_new_refresh():
    """Test the NEW refresh logic"""
    
    # Get Intel prediction
    with Session(engine) as db:
        prediction = db.query(Prediction).join(
            Entity, Prediction.entity_id == Entity.entity_id
        ).filter(
            Entity.entity_name.like('%Intel%')
        ).order_by(Prediction.created_at.desc()).first()
        
        if not prediction:
            logger.error("No Intel prediction found")
            return
        
        logger.info(f"Found prediction: {prediction.prediction_id}")
        logger.info(f"Entity: {prediction.entity_id} - {prediction.entity.entity_name if prediction.entity else 'Unknown'}")
    
    # Simulate the NEW refresh button logic
    logger.info("\n" + "="*60)
    logger.info("SIMULATING NEW REFRESH BUTTON LOGIC")
    logger.info("="*60 + "\n")
    
    from src.gui.tabs.predictions import _format_saved_performance
    import uuid
    from datetime import datetime
    
    with Session(engine) as db:
        pred = db.query(Prediction).filter(
            Prediction.prediction_id == prediction.prediction_id
        ).first()
        
        entity = db.query(Entity).filter(
            Entity.entity_id == pred.entity_id
        ).first()
        
        outcome = db.query(PredictionOutcome).filter(
            PredictionOutcome.prediction_id == prediction.prediction_id
        ).first()
        
        if not outcome:
            logger.info("Creating new outcome...")
            outcome = PredictionOutcome(
                outcome_id=uuid.uuid4(),
                prediction_id=prediction.prediction_id,
                actual_return=0,
                error=0,
                direction_correct=False,
                within_confidence_interval=True,
                sharpe_contribution=0,
                evaluation_timestamp=datetime.now(),
                created_at=datetime.now()
            )
            db.add(outcome)
            db.flush()
        
        # Calculate using Details view logic (load_live_prices=True)
        logger.info("Calculating performance with Details view logic...")
        performance = _format_saved_performance(pred, entity, outcome, load_live_prices=True)
        
        logger.info(f"\n📊 Performance calculated:")
        logger.info(f"   total_return_pct: {performance.get('total_return_pct')}%")
        logger.info(f"   is_correct: {performance.get('is_correct')}")
        logger.info(f"   prediction_price: ${performance.get('prediction_price')}")
        logger.info(f"   current_price: ${performance.get('current_price')}")
        
        # Save to database
        outcome.actual_return = performance.get('total_return_pct', 0)
        outcome.error = abs(performance.get('total_return_pct', 0))
        outcome.direction_correct = performance.get('is_correct', False)
        
        db.commit()
        
        logger.info(f"\n💾 Saved to database: {outcome.actual_return}%")
    
    # Verify
    with Session(engine) as db:
        saved = db.query(PredictionOutcome).filter(
            PredictionOutcome.prediction_id == prediction.prediction_id
        ).first()
        
        logger.info(f"\n✅ VERIFICATION:")
        logger.info(f"   actual_return: {saved.actual_return}%")
        logger.info(f"   direction_correct: {saved.direction_correct}")
        
        if abs(saved.actual_return) > 1:
            logger.info(f"\n🎉 SUCCESS! Value is significant: {saved.actual_return}%")
        elif abs(saved.actual_return) > 0.01:
            logger.info(f"\n✅ Value is small but not zero: {saved.actual_return}%")
        else:
            logger.warning(f"\n⚠️ Value is very small: {saved.actual_return}%")

if __name__ == "__main__":
    test_new_refresh()
