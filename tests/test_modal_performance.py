"""
Quick test to verify modal shows saved performance without refetching
"""
from sqlalchemy import desc

from src.gui.tabs import predictions
from src.models.database import SessionLocal
from src.models.predictions import Prediction, PredictionOutcome

engine = SessionLocal().get_bind()

# Get a prediction that has outcome data
with SessionLocal() as db:
    # Find a prediction with saved outcome
    pred_with_outcome = db.query(Prediction).join(
        PredictionOutcome,
        Prediction.prediction_id == PredictionOutcome.prediction_id
    ).order_by(desc(PredictionOutcome.evaluation_timestamp)).first()

    if not pred_with_outcome:
        print("❌ No predictions with saved outcomes found")
        print("Run the refresh button on a prediction first!")
        exit()

    print(f"✅ Found prediction with outcome: {pred_with_outcome.prediction_id}")

    # Get the outcome to show what's saved
    outcome = db.query(PredictionOutcome).filter(
        PredictionOutcome.prediction_id == pred_with_outcome.prediction_id
    ).first()

    print("📊 Saved performance:")
    print(f"   - Return: {(outcome.actual_return or 0) * 100:.2f}%")
    print(f"   - Correct: {outcome.direction_correct}")
    print(f"   - Timestamp: {outcome.evaluation_timestamp}")

# Now test get_prediction_details WITHOUT load_performance=True
print("\n🔍 Testing modal display (load_performance=False)...")
title, body, _ = predictions.get_prediction_details(
    engine,
    pred_with_outcome.prediction_id,
    load_performance=False  # This is what happens when modal opens
)

# Check if performance is in the body content
body_str = str(body)
if "Live Performance" in body_str and "Return Since Prediction" in body_str:
    print("✅ SUCCESS: Modal shows saved performance without refetching!")
    if "not loaded" in body_str or "Click the" in body_str:
        print("⚠️ WARNING: Also shows 'not loaded' message")
    else:
        print("✅ Performance data is displayed correctly")
else:
    print("❌ FAILED: Performance not shown in modal")
    if "not loaded" in body_str:
        print("   Modal shows 'not loaded' placeholder")

print("\n✅ Test complete!")
