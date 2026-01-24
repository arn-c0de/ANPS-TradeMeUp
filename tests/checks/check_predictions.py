"""Quick script to check predictions in database"""
from sqlalchemy import create_engine, func
from sqlalchemy.orm import Session
from src.models.predictions import Prediction
from src.models.entities import Entity
from src.config.settings import settings

engine = create_engine(settings.database_url)

with Session(engine) as db:
    # Count predictions
    pred_count = db.query(func.count(Prediction.prediction_id)).scalar()
    print(f"Total Predictions: {pred_count}")
    
    if pred_count > 0:
        # Show sample predictions
        preds = db.query(Prediction).limit(5).all()
        print("\nSample Predictions:")
        for p in preds:
            entity = db.query(Entity).filter(Entity.entity_id == p.entity_id).first()
            print(f"  - {p.prediction_id}: {entity.entity_name if entity else p.entity_id} | {p.horizon} | {p.created_at}")
    else:
        print("\n⚠️ No predictions found in database!")
        print("Run the prediction agent to create predictions first.")
