"""
Quick test to check if callbacks are working
"""
import sys

from sqlalchemy.orm import Session

from src.models.database import SessionLocal

# Test prediction loading
engine = SessionLocal().get_bind()

with Session(engine) as db:
    from src.models.entities import Entity
    from src.models.predictions import Prediction

    pred = db.query(Prediction).first()
    if pred:
        print(f"✓ Found prediction: {pred.prediction_id}")
        print(f"  Entity: {pred.entity_id}")
        print(f"  Created: {pred.created_at}")
        print(f"  Horizon: {pred.horizon}")

        entity = db.query(Entity).filter(Entity.entity_id == pred.entity_id).first()
        if entity:
            print(f"  Entity name: {entity.entity_name}")

            # Test performance service
            from src.services.prediction_performance_service import prediction_performance_service

            print(f"\n🔄 Testing performance calculation for {entity.entity_id}...")
            perf = prediction_performance_service.get_prediction_performance(pred, entity)

            if perf:
                print("✓ Performance calculated successfully!")
                print(f"  Current price: ${perf.get('current_price')}")
                print(f"  Return: {perf.get('total_return_pct'):.2f}%")
                print(f"  Correct: {perf.get('is_correct')}")
            else:
                print("✗ Could not calculate performance")
        else:
            print("✗ Entity not found")
    else:
        print("✗ No predictions found in database")

print("\n" + "="*60)
print("If you see errors above, that's why the refresh button doesn't work!")
print("="*60)
