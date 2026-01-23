"""Test if update logic works correctly"""
from sqlalchemy import create_engine, update
from sqlalchemy.orm import Session
from datetime import datetime

engine = create_engine('sqlite:///trademeup.db')

with Session(engine) as db:
    from src.models.predictions import Prediction, PredictionOutcome
    from src.models.entities import Entity
    from src.services.prediction_performance_service import prediction_performance_service
    
    # Find a prediction that already has performance data
    outcome = db.query(PredictionOutcome).first()
    
    if outcome:
        print(f"✓ Found existing outcome:")
        print(f"  Prediction ID: {outcome.prediction_id}")
        print(f"  Old Return: {outcome.actual_return}%")
        print(f"  Old Timestamp: {outcome.evaluation_timestamp}")
        
        # Get the prediction
        pred = db.query(Prediction).filter(
            Prediction.prediction_id == outcome.prediction_id
        ).first()
        
        if pred:
            entity = db.query(Entity).filter(
                Entity.entity_id == pred.entity_id
            ).first()
            
            if entity:
                print(f"\n🔄 Recalculating performance for {entity.entity_name}...")
                
                # Calculate new performance
                perf_data = prediction_performance_service.get_prediction_performance(pred, entity)
                
                if perf_data:
                    print(f"  New Return: {perf_data.get('total_return_pct')}%")
                    
                    # Save it (should UPDATE existing record)
                    success = prediction_performance_service.save_prediction_performance(
                        str(outcome.prediction_id), perf_data, db
                    )
                    
                    if success:
                        print(f"\n✅ Update successful!")
                        
                        # Verify the update
                        updated = db.query(PredictionOutcome).filter(
                            PredictionOutcome.prediction_id == outcome.prediction_id
                        ).first()
                        
                        print(f"  Updated Return: {updated.actual_return}%")
                        print(f"  Updated Timestamp: {updated.evaluation_timestamp}")
                        print(f"\n✓ Timestamp changed: {updated.evaluation_timestamp != outcome.evaluation_timestamp}")
                    else:
                        print(f"\n❌ Update failed!")
                else:
                    print(f"  ⚠️ Could not calculate performance")
    else:
        print("❌ No existing outcomes found - run a refresh first")

print("\n" + "="*60)
print("If you see '✓ Timestamp changed: True', the update works!")
print("="*60)
