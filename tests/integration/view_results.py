"""View current pipeline results from database."""
import sys
from pathlib import Path

project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

import json

from sqlalchemy import desc, func

from src.models.analysis import ImpactScore, MarketRegime, SurpriseScore
from src.models.data_quality import DataQualityScore
from src.models.database import SessionLocal
from src.models.entities import Entity, NewsEntityMapping
from src.models.predictions import Prediction
from src.models.processed_news import ProcessedNews
from src.models.raw_news import RawNews


def main():
    db = SessionLocal()

    print("\n" + "="*80)
    print("📊 TRADEMEUP MVP - CURRENT RESULTS")
    print("="*80 + "\n")

    # 1. Data Ingestion Results
    print("📥 1. DATA INGESTION")
    print("-" * 80)
    total_articles = db.query(func.count(RawNews.news_id)).scalar()
    by_source = db.query(
        RawNews.source,
        func.count(RawNews.news_id).label('count')
    ).group_by(RawNews.source).all()

    print(f"   Total Articles: {total_articles}")
    for source, count in by_source:
        print(f"   - {source}: {count}")

    # Show latest articles
    latest = db.query(RawNews).order_by(desc(RawNews.published_at)).limit(5).all()
    print("\n   Latest 5 Articles:")
    for article in latest:
        print(f"   • {article.title[:70]}... ({article.source})")

    # 2. Quality Assessment
    print("\n📋 2. DATA QUALITY ASSESSMENT")
    print("-" * 80)
    total_assessed = db.query(func.count(DataQualityScore.news_id)).scalar()
    avg_quality = db.query(func.avg(DataQualityScore.quality_score)).scalar()

    # Count quality distribution manually
    high_quality = db.query(func.count(DataQualityScore.news_id)).filter(
        DataQualityScore.quality_score >= 0.8
    ).scalar()
    medium_quality = db.query(func.count(DataQualityScore.news_id)).filter(
        DataQualityScore.quality_score >= 0.6,
        DataQualityScore.quality_score < 0.8
    ).scalar()
    low_quality = db.query(func.count(DataQualityScore.news_id)).filter(
        DataQualityScore.quality_score < 0.6
    ).scalar()

    print(f"   Total Assessed: {total_assessed}")
    print(f"   Average Quality: {avg_quality:.2f}" if avg_quality else "   Average Quality: N/A")
    print(f"   - High Quality (≥0.8): {high_quality}")
    print(f"   - Medium Quality (0.6-0.8): {medium_quality}")
    print(f"   - Low Quality (<0.6): {low_quality}")

    # 3. Content Understanding
    print("\n🧠 3. CONTENT UNDERSTANDING (LLM)")
    print("-" * 80)
    total_processed = db.query(func.count(ProcessedNews.news_id)).scalar()

    by_event = db.query(
        ProcessedNews.event_type,
        func.count(ProcessedNews.news_id).label('count')
    ).group_by(ProcessedNews.event_type).all()

    print(f"   Total Processed: {total_processed}")
    if by_event:
        print("   Event Types:")
        for event_type, count in by_event:
            print(f"   - {event_type}: {count}")

    # Show some analyzed articles
    if total_processed > 0:
        samples = db.query(ProcessedNews).limit(3).all()
        print("\n   Sample Analysis:")
        for sample in samples:
            news = db.query(RawNews).filter(RawNews.news_id == sample.news_id).first()
            sentiment_val = sample.sentiment.get('overall', 0) if sample.sentiment else 0
            print(f"   • {news.title[:60]}...")
            print(f"     Event: {sample.event_type}, Sentiment: {sentiment_val:.2f}")
            if sample.summary_short:
                print(f"     Summary: {sample.summary_short[:100]}...")

    # 4. Entity Mapping
    print("\n🏢 4. ENTITY MAPPING")
    print("-" * 80)
    total_entities = db.query(func.count(Entity.entity_id)).scalar()
    total_mappings = db.query(func.count(NewsEntityMapping.mapping_id)).scalar()

    by_type = db.query(
        Entity.entity_type,
        func.count(Entity.entity_id).label('count')
    ).group_by(Entity.entity_type).all()

    print(f"   Total Entities: {total_entities}")
    print(f"   Total Mappings: {total_mappings}")
    if by_type:
        print("   Entity Types:")
        for entity_type, count in by_type:
            print(f"   - {entity_type}: {count}")

    # Show top entities
    if total_entities > 0:
        top_entities = db.query(Entity).limit(5).all()
        print("\n   Top Entities:")
        for entity in top_entities:
            print(f"   • {entity.entity_name} ({entity.entity_type})")

    # 5. Market Regime
    print("\n🌡️  5. MARKET REGIME DETECTION")
    print("-" * 80)
    latest_regime = db.query(MarketRegime).order_by(desc(MarketRegime.created_at)).first()
    if latest_regime:
        print("   Current Regime:")
        regime_data = latest_regime.regime
        for key, value in regime_data.items():
            print(f"   - {key.replace('_', ' ').title()}: {value}")
        print(f"   Detected at: {latest_regime.created_at}")
    else:
        print("   No regime data yet")

    # 6. Impact Scores
    print("\n⚡ 6. IMPACT SCORING")
    print("-" * 80)
    total_impacts = db.query(func.count(ImpactScore.score_id)).scalar()
    avg_impact = db.query(func.avg(ImpactScore.impact_score)).scalar()

    high_impact = db.query(func.count(ImpactScore.score_id)).filter(
        ImpactScore.impact_score >= 0.7
    ).scalar()

    print(f"   Total Impact Scores: {total_impacts}")
    if avg_impact:
        print(f"   Average Impact: {avg_impact:.2f}")
    print(f"   High Impact (>0.7): {high_impact}")

    # Show top impact news
    if total_impacts > 0:
        top_impacts = db.query(ImpactScore).order_by(
            desc(ImpactScore.impact_score)
        ).limit(5).all()
        print("\n   Top Impact News:")
        for impact in top_impacts:
            news = db.query(RawNews).filter(RawNews.news_id == impact.news_id).first()
            if news:
                print(f"   • {news.title[:60]}... (Impact: {impact.impact_score:.2f})")

    # 7. Predictions
    print("\n🎯 7. PREDICTIONS")
    print("-" * 80)
    total_predictions = db.query(func.count(Prediction.prediction_id)).scalar()

    avg_confidence = db.query(func.avg(Prediction.confidence)).scalar()

    print(f"   Total Predictions: {total_predictions}")
    if avg_confidence:
        print(f"   Average Confidence: {avg_confidence:.2f}")

    # Show latest predictions
    if total_predictions > 0:
        latest_preds = db.query(Prediction).order_by(
            desc(Prediction.created_at)
        ).limit(5).all()
        print("\n   Latest Predictions:")
        for pred in latest_preds:
            entity = db.query(Entity).filter(Entity.entity_id == pred.entity_id).first()
            if entity:
                # Get direction from probabilities
                probs = pred.direction_probabilities or {}
                direction = max(probs, key=probs.get) if probs else "unknown"
                exp_ret_dict = pred.expected_return or {}
                expected_ret = exp_ret_dict.get('mean', 0) if isinstance(exp_ret_dict, dict) else 0
                print(f"   • {entity.entity_name}: {direction} "
                      f"(confidence: {pred.confidence:.2f}, exp return: {expected_ret:.2%})")

    print("\n" + "="*80)
    print("✅ Results summary complete!")
    print("="*80 + "\n")

    db.close()

if __name__ == "__main__":
    main()
