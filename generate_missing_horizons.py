"""
Generate missing horizon predictions (1d and 20d) for all existing 5d predictions
"""
from src.models.database import SessionLocal
from src.models.predictions import Prediction
from src.agents.prediction_agent import PredictionAgent
from datetime import datetime

def main():
    """Generate missing horizon predictions"""
    db = SessionLocal()

    try:
        print("=" * 70)
        print("GENERATING MISSING HORIZON PREDICTIONS")
        print("=" * 70)

        # Initialize prediction agent
        pred_agent = PredictionAgent(db)

        # Get all existing predictions
        all_predictions = db.query(Prediction).all()

        print(f"\nFound {len(all_predictions)} existing predictions")

        # Group by entity + news_id
        from collections import defaultdict
        by_entity_news = defaultdict(set)

        for pred in all_predictions:
            news_ids = pred.related_news_ids or []
            if news_ids:
                news_id = news_ids[0] if isinstance(news_ids, list) else news_ids
                key = (pred.entity_id, str(news_id))
                by_entity_news[key].add(pred.horizon)

        print(f"Found {len(by_entity_news)} unique entity-news combinations")

        # Define expected horizons
        expected_horizons = {'1d', '5d', '20d'}

        # Find missing horizons
        to_generate = []
        for (entity_id, news_id), existing_horizons in by_entity_news.items():
            missing = expected_horizons - existing_horizons
            if missing:
                to_generate.append((entity_id, news_id, missing))

        print(f"Found {len(to_generate)} entity-news pairs with missing horizons")
        print(f"Starting generation at: {datetime.now()}\n")

        stats = {
            'total': 0,
            'created': 0,
            'skipped': 0,
            'errors': 0
        }

        for i, (entity_id, news_id, missing_horizons) in enumerate(to_generate, 1):
            print(f"[{i}/{len(to_generate)}] Entity: {entity_id}, News: {news_id[:8]}...")
            print(f"  Missing horizons: {sorted(missing_horizons)}")

            for horizon in sorted(missing_horizons):
                try:
                    prediction = pred_agent.generate_prediction(
                        entity_id=entity_id,
                        news_id=news_id,
                        horizon=horizon
                    )

                    stats['total'] += 1

                    if prediction:
                        print(f"    [OK] Created {horizon} prediction (confidence: {prediction.confidence:.2%})")
                        stats['created'] += 1
                    else:
                        print(f"    [SKIP] Skipped {horizon} (low confidence or no impact)")
                        stats['skipped'] += 1

                except Exception as e:
                    print(f"    [ERROR] Creating {horizon}: {e}")
                    stats['errors'] += 1

        print("\n" + "=" * 70)
        print("RESULTS")
        print("=" * 70)
        print(f"Total attempts: {stats['total']}")
        print(f"Created: {stats['created']}")
        print(f"Skipped: {stats['skipped']}")
        print(f"Errors: {stats['errors']}")

        # Show new totals
        new_total = db.query(Prediction).count()
        by_horizon = {}
        for horizon in expected_horizons:
            count = db.query(Prediction).filter(Prediction.horizon == horizon).count()
            by_horizon[horizon] = count

        print("\n" + "=" * 70)
        print("FINAL PREDICTION COUNTS")
        print("=" * 70)
        print(f"Total predictions: {new_total}")
        for horizon in sorted(expected_horizons):
            print(f"  {horizon}: {by_horizon.get(horizon, 0)}")

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
