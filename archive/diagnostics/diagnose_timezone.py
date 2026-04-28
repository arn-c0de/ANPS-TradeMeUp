"""
Quick diagnostic script to check timezone handling
"""
from datetime import datetime, timedelta, timezone
from sqlalchemy.orm import Session
from src.models.database import get_scoped_session, engine
from src.models.raw_news import RawNews
from src.models.processed_news import ProcessedNews
from src.models.predictions import Prediction
from sqlalchemy import func

print("=" * 80)
print("TIMEZONE DIAGNOSTIC")
print("=" * 80)

with Session(engine) as db:
    # Check current time
    now = datetime.now(timezone.utc)
    local_now = datetime.now()
    
    print(f"\n🕒 Current Times:")
    print(f"   UTC now:   {now}")
    print(f"   Local now: {local_now}")
    print(f"   Difference: {local_now - now.replace(tzinfo=None)}")
    
    hour_ago = now - timedelta(hours=1)
    day_ago = now - timedelta(hours=24)
    
    print(f"\n⏰ Time Windows:")
    print(f"   Now:        {now}")
    print(f"   1h ago:     {hour_ago}")
    print(f"   24h ago:    {day_ago}")
    
    # Check latest timestamps
    print(f"\n📰 Latest Raw News:")
    latest_news = db.query(RawNews).order_by(RawNews.fetched_at.desc()).limit(5).all()
    for i, news in enumerate(latest_news, 1):
        print(f"   {i}. Fetched: {news.fetched_at} (TZ: {news.fetched_at.tzinfo})")
        time_diff = now - news.fetched_at
        print(f"      Age: {time_diff}")
        print(f"      Within 1h? {news.fetched_at >= hour_ago}")
    
    print(f"\n🧠 Latest Processed News:")
    latest_processed = db.query(ProcessedNews).order_by(ProcessedNews.processing_timestamp.desc()).limit(5).all()
    for i, proc in enumerate(latest_processed, 1):
        print(f"   {i}. Processed: {proc.processing_timestamp} (TZ: {proc.processing_timestamp.tzinfo})")
        time_diff = now - proc.processing_timestamp
        print(f"      Age: {time_diff}")
        print(f"      Within 1h? {proc.processing_timestamp >= hour_ago}")
    
    print(f"\n🔮 Latest Predictions:")
    latest_predictions = db.query(Prediction).order_by(Prediction.created_at.desc()).limit(5).all()
    for i, pred in enumerate(latest_predictions, 1):
        print(f"   {i}. Created: {pred.created_at} (TZ: {pred.created_at.tzinfo})")
        time_diff = now - pred.created_at
        print(f"      Age: {time_diff}")
        print(f"      Within 1h? {pred.created_at >= hour_ago}")
    
    # Count statistics
    print(f"\n📊 Statistics:")
    total_news = db.query(func.count(RawNews.news_id)).scalar() or 0
    news_1h = db.query(func.count(RawNews.news_id)).filter(RawNews.fetched_at >= hour_ago).scalar() or 0
    news_24h = db.query(func.count(RawNews.news_id)).filter(RawNews.fetched_at >= day_ago).scalar() or 0
    
    print(f"   Total news: {total_news}")
    print(f"   News in last 1h: {news_1h}")
    print(f"   News in last 24h: {news_24h}")
    
    total_processed = db.query(func.count(ProcessedNews.news_id)).scalar() or 0
    processed_1h = db.query(func.count(ProcessedNews.news_id)).filter(ProcessedNews.processing_timestamp >= hour_ago).scalar() or 0
    processed_24h = db.query(func.count(ProcessedNews.news_id)).filter(ProcessedNews.processing_timestamp >= day_ago).scalar() or 0
    
    print(f"\n   Total processed: {total_processed}")
    print(f"   Processed in last 1h: {processed_1h}")
    print(f"   Processed in last 24h: {processed_24h}")
    
    total_predictions = db.query(func.count(Prediction.prediction_id)).scalar() or 0
    predictions_1h = db.query(func.count(Prediction.prediction_id)).filter(Prediction.created_at >= hour_ago).scalar() or 0
    predictions_24h = db.query(func.count(Prediction.prediction_id)).filter(Prediction.created_at >= day_ago).scalar() or 0
    
    print(f"\n   Total predictions: {total_predictions}")
    print(f"   Predictions in last 1h: {predictions_1h}")
    print(f"   Predictions in last 24h: {predictions_24h}")

print("\n" + "=" * 80)
print("DIAGNOSTIC COMPLETE")
print("=" * 80)
