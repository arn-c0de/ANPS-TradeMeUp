"""
Check why so few predictions are created from processed news
"""

import logging

from sqlalchemy import create_engine, func
from sqlalchemy.orm import Session

from src.config.settings import settings
from src.models.entities import Entity
from src.models.predictions import Prediction
from src.models.processed_news import ProcessedNews
from src.models.raw_news import RawNews

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

engine = create_engine(settings.database_url)

def check_prediction_gap():
    """Analyze why predictions are not created from processed news"""

    with Session(engine) as db:
        # Get counts
        total_raw = db.query(func.count(RawNews.news_id)).scalar()
        total_processed = db.query(func.count(ProcessedNews.news_id)).scalar()
        total_predictions = db.query(func.count(Prediction.prediction_id)).scalar()

        logger.info("="*70)
        logger.info("📊 STATISTICS")
        logger.info("="*70)
        logger.info(f"Total Raw News: {total_raw}")
        logger.info(f"Total Processed News: {total_processed}")
        logger.info(f"Total Predictions: {total_predictions}")
        logger.info(f"Conversion Rate: {(total_predictions/total_processed*100):.1f}% (Processed → Predictions)")
        logger.info("")

        # Find processed news WITHOUT predictions
        processed_with_predictions = db.query(Prediction.related_news_ids).all()
        news_ids_with_predictions = set()
        for row in processed_with_predictions:
            if row[0]:  # related_news_ids
                news_ids_with_predictions.update(row[0])

        logger.info(f"News IDs that have predictions: {len(news_ids_with_predictions)}")

        # Get processed news without predictions
        processed_without_pred = db.query(ProcessedNews).filter(
            ~ProcessedNews.news_id.in_(news_ids_with_predictions)
        ).limit(20).all()

        logger.info("="*70)
        logger.info("🔍 SAMPLE: Processed News WITHOUT Predictions (showing 20)")
        logger.info("="*70)

        reasons = {
            'no_entity': 0,
            'no_event_type': 0,
            'no_impact_score': 0,
            'no_surprise_score': 0,
            'low_impact': 0,
            'low_surprise': 0,
            'has_data': 0
        }

        for pn in processed_without_pred:
            logger.info(f"\nNews ID: {pn.news_id}")
            logger.info(f"  Event Type: {pn.event_type or 'MISSING'}")
            logger.info(f"  Event Subtype: {pn.event_subtype or 'None'}")
            logger.info(f"  Confidence: {pn.confidence or 'MISSING'}")
            logger.info(f"  Summary: {pn.summary_short[:80] if pn.summary_short else 'MISSING'}...")

            # Check reasons
            if not pn.event_type:
                reasons['no_event_type'] += 1
                logger.info("  ❌ Reason: No event type")
            elif not pn.confidence or pn.confidence < 0.3:
                reasons['low_impact'] += 1
                logger.info(f"  ⚠️ Reason: Low confidence ({pn.confidence})")
            else:
                reasons['has_data'] += 1
                logger.info("  ✅ Has data but no prediction!")

        logger.info("\n" + "="*70)
        logger.info("📈 REASON BREAKDOWN")
        logger.info("="*70)
        for reason, count in reasons.items():
            logger.info(f"{reason}: {count}")

        # Check for impact/surprise score distribution
        logger.info("\n" + "="*70)
        logger.info("📊 CONFIDENCE SCORE DISTRIBUTION")
        logger.info("="*70)

        high_confidence = db.query(func.count(ProcessedNews.news_id)).filter(
            ProcessedNews.confidence >= 0.5
        ).scalar()

        has_confidence = db.query(func.count(ProcessedNews.news_id)).filter(
            ProcessedNews.confidence.isnot(None)
        ).scalar()

        logger.info(f"Processed news with confidence >= 0.5: {high_confidence}")
        logger.info(f"Processed news with any confidence: {has_confidence}")

        # Check entities
        logger.info("\n" + "="*70)
        logger.info("🏢 ENTITY STATISTICS")
        logger.info("="*70)

        total_entities = db.query(func.count(Entity.entity_id)).scalar()
        company_entities = db.query(func.count(Entity.entity_id)).filter(
            Entity.entity_type == 'company'
        ).scalar()

        logger.info(f"Total entities in DB: {total_entities}")
        logger.info(f"Company entities: {company_entities}")

        # Check predictions by entity
        logger.info("\n" + "="*70)
        logger.info("🎯 TOP ENTITIES WITH PREDICTIONS")
        logger.info("="*70)

        pred_by_entity = db.query(
            Prediction.entity_id,
            func.count(Prediction.prediction_id).label('count')
        ).group_by(Prediction.entity_id).order_by(func.count(Prediction.prediction_id).desc()).limit(10).all()

        for entity_id, count in pred_by_entity:
            entity = db.query(Entity).filter(Entity.entity_id == entity_id).first()
            entity_name = entity.entity_name if entity else 'Unknown'
            logger.info(f"{entity_id} ({entity_name}): {count} predictions")

if __name__ == "__main__":
    check_prediction_gap()
