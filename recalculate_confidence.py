"""
Recalculate confidence for all existing predictions using new dynamic formula
"""
import numpy as np
from src.models.database import SessionLocal
from src.models.predictions import Prediction
from src.models.analysis import ImpactScore
from datetime import datetime

def recalculate_confidence(prediction: Prediction, impact_score: float) -> float:
    """
    Recalculate confidence using the new dynamic formula

    Args:
        prediction: Prediction object
        impact_score: Impact score value

    Returns:
        New confidence value
    """
    # Get direction probabilities
    probs = prediction.direction_probabilities or {}
    max_prob = max(probs.values()) if probs else 0.33

    # Dynamic confidence based on impact and max probability
    # Higher impact and stronger directional signal = higher confidence
    base_confidence = 0.45 + (impact_score * 0.25)  # 0.45-0.70 based on impact
    directional_boost = (max_prob - 0.33) * 0.3  # Boost if strong direction
    confidence = np.clip(base_confidence + directional_boost, 0.40, 0.85)

    return float(confidence)


def main():
    """Recalculate all prediction confidences"""
    db = SessionLocal()

    try:
        print("=" * 70)
        print("RECALCULATING PREDICTION CONFIDENCES")
        print("=" * 70)

        # Get all predictions
        predictions = db.query(Prediction).all()
        total = len(predictions)

        print(f"\nFound {total} predictions to update")
        print(f"Started at: {datetime.now()}\n")

        updated = 0
        skipped = 0
        errors = 0

        confidence_changes = []

        for i, pred in enumerate(predictions, 1):
            try:
                # Find the related impact score
                # Predictions have related_news_ids as JSON array
                news_ids = pred.related_news_ids or []

                if not news_ids:
                    print(f"[{i}/{total}] Skipped {pred.prediction_id}: No related news")
                    skipped += 1
                    continue

                # Get first news_id (primary news for this prediction)
                news_id = news_ids[0] if isinstance(news_ids, list) else news_ids

                # Find impact score
                impact = db.query(ImpactScore).filter(
                    ImpactScore.news_id == news_id,
                    ImpactScore.entity_id == pred.entity_id
                ).first()

                if not impact:
                    print(f"[{i}/{total}] Skipped {pred.prediction_id}: No impact score found")
                    skipped += 1
                    continue

                # Calculate new confidence
                old_confidence = pred.confidence
                new_confidence = recalculate_confidence(pred, impact.impact_score)

                # Update prediction
                pred.confidence = new_confidence

                # Track change
                change = new_confidence - old_confidence
                confidence_changes.append({
                    'entity': pred.entity_id,
                    'old': old_confidence,
                    'new': new_confidence,
                    'change': change,
                    'impact': impact.impact_score
                })

                updated += 1

                # Progress indicator
                if i % 5 == 0 or i == total:
                    print(f"[{i}/{total}] {pred.entity_id}: {old_confidence:.2%} → {new_confidence:.2%} (Δ{change:+.2%})")

            except Exception as e:
                print(f"[{i}/{total}] ERROR processing {pred.prediction_id}: {e}")
                errors += 1
                continue

        # Commit all changes
        db.commit()

        print("\n" + "=" * 70)
        print("RESULTS")
        print("=" * 70)
        print(f"Total predictions: {total}")
        print(f"Updated: {updated}")
        print(f"Skipped: {skipped}")
        print(f"Errors: {errors}")

        if confidence_changes:
            print("\n" + "=" * 70)
            print("CONFIDENCE STATISTICS")
            print("=" * 70)

            changes = [c['change'] for c in confidence_changes]
            old_vals = [c['old'] for c in confidence_changes]
            new_vals = [c['new'] for c in confidence_changes]

            print(f"Old confidence range: {min(old_vals):.2%} - {max(old_vals):.2%}")
            print(f"New confidence range: {min(new_vals):.2%} - {max(new_vals):.2%}")
            print(f"Average change: {np.mean(changes):+.2%}")
            print(f"Max increase: {max(changes):+.2%}")
            print(f"Max decrease: {min(changes):+.2%}")

            print("\n" + "=" * 70)
            print("TOP 10 CONFIDENCE CHANGES")
            print("=" * 70)
            print(f"{'Entity':<15} {'Impact':<8} {'Old':<8} {'New':<8} {'Change':<8}")
            print("-" * 70)

            # Sort by absolute change
            confidence_changes.sort(key=lambda x: abs(x['change']), reverse=True)

            for change in confidence_changes[:10]:
                print(f"{change['entity']:<15} {change['impact']:<8.3f} "
                      f"{change['old']:<8.2%} {change['new']:<8.2%} {change['change']:+8.2%}")

        print("\n" + "=" * 70)
        print(f"Completed at: {datetime.now()}")
        print("=" * 70)

    except Exception as e:
        db.rollback()
        print(f"\nFATAL ERROR: {e}")
        import traceback
        traceback.print_exc()
    finally:
        db.close()


if __name__ == "__main__":
    main()
