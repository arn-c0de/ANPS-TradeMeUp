"""
Test script to verify timezone-aware datetime handling in PostgreSQL
"""
from datetime import datetime, timedelta, timezone
from sqlalchemy.orm import Session
from src.models.database import get_scoped_session, utc_now
from src.models.raw_news import RawNews
from src.models.processed_news import ProcessedNews
from src.models.predictions import Prediction
from sqlalchemy import func

def test_timezone_queries():
    """Test that timezone-aware queries work correctly"""
    print("=" * 80)
    print("Testing Timezone-Aware DateTime Handling")
    print("=" * 80)
    
    with get_scoped_session() as db:
        # Test 1: Check current time handling
        now = utc_now()
        print(f"\n✓ Current UTC time (timezone-aware): {now}")
        print(f"  Timezone info: {now.tzinfo}")
        
        # Test 2: Check database timestamps
        print("\n" + "=" * 80)
        print("Checking Recent Database Timestamps")
        print("=" * 80)
        
        # Check raw news
        latest_news = db.query(RawNews).order_by(RawNews.fetched_at.desc()).first()
        if latest_news:
            print(f"\n📰 Latest Raw News:")
            print(f"   Fetched at: {latest_news.fetched_at}")
            print(f"   Timezone info: {latest_news.fetched_at.tzinfo if latest_news.fetched_at else 'None'}")
            print(f"   Created at: {latest_news.created_at}")
            print(f"   Timezone info: {latest_news.created_at.tzinfo if latest_news.created_at else 'None'}")
        
        # Check processed news
        latest_processed = db.query(ProcessedNews).order_by(ProcessedNews.processing_timestamp.desc()).first()
        if latest_processed:
            print(f"\n🧠 Latest Processed News:")
            print(f"   Processing timestamp: {latest_processed.processing_timestamp}")
            print(f"   Timezone info: {latest_processed.processing_timestamp.tzinfo if latest_processed.processing_timestamp else 'None'}")
        
        # Check predictions
        latest_prediction = db.query(Prediction).order_by(Prediction.created_at.desc()).first()
        if latest_prediction:
            print(f"\n🔮 Latest Prediction:")
            print(f"   Created at: {latest_prediction.created_at}")
            print(f"   Timezone info: {latest_prediction.created_at.tzinfo if latest_prediction.created_at else 'None'}")
        
        # Test 3: Test time-based queries
        print("\n" + "=" * 80)
        print("Testing Time-Based Queries")
        print("=" * 80)
        
        hour_ago = now - timedelta(hours=1)
        day_ago = now - timedelta(hours=24)
        
        print(f"\n⏰ Time windows:")
        print(f"   Now: {now}")
        print(f"   1 hour ago: {hour_ago}")
        print(f"   24 hours ago: {day_ago}")
        
        # Count articles in different time windows
        total_news = db.query(func.count(RawNews.news_id)).scalar() or 0
        news_1h = db.query(func.count(RawNews.news_id)).filter(RawNews.fetched_at >= hour_ago).scalar() or 0
        news_24h = db.query(func.count(RawNews.news_id)).filter(RawNews.fetched_at >= day_ago).scalar() or 0
        
        print(f"\n📊 Query Results:")
        print(f"   Total articles: {total_news}")
        print(f"   Articles in last 1h: {news_1h}")
        print(f"   Articles in last 24h: {news_24h}")
        
        # Check if counts make sense
        if news_24h > 0 and news_1h == 0:
            print("\n⚠️  WARNING: Found articles in 24h window but none in 1h window")
            print("   This might indicate a timezone issue if articles were recently added")
            
            # Show the most recent article
            if latest_news:
                time_diff = now - latest_news.fetched_at
                print(f"\n   Most recent article was fetched {time_diff} ago")
                print(f"   Article timestamp: {latest_news.fetched_at}")
                print(f"   Current time: {now}")
        elif news_1h > 0:
            print(f"\n✓ Found {news_1h} articles in the last hour - timezone handling appears correct!")
        
        # Test 4: Check for naive datetimes
        print("\n" + "=" * 80)
        print("Checking for Naive DateTimes (Should be None)")
        print("=" * 80)
        
        naive_count = 0
        sample_size = 10
        recent_news = db.query(RawNews).order_by(RawNews.fetched_at.desc()).limit(sample_size).all()
        
        print(f"\nChecking {len(recent_news)} recent articles...")
        for news in recent_news:
            if news.fetched_at and news.fetched_at.tzinfo is None:
                naive_count += 1
                print(f"   ⚠️  Naive datetime found: {news.fetched_at} (article {news.news_id})")
        
        if naive_count == 0:
            print("   ✓ All timestamps are timezone-aware!")
        else:
            print(f"   ⚠️  Found {naive_count}/{len(recent_news)} naive datetimes")
            print("   This might cause query issues. Consider running a migration to fix existing data.")
        
        print("\n" + "=" * 80)
        print("Test Complete")
        print("=" * 80)

if __name__ == "__main__":
    test_timezone_queries()
