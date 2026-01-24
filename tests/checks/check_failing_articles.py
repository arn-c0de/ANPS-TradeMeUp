"""Check what these persistently failing articles are about"""

from src.models.database import SessionLocal
from src.models.raw_news import RawNews

db = SessionLocal()

failing_ids = [
    '6bf912bb-5899-4e3d-8d24-69ac91bb038e',
    '8bb7ca8e-49d9-4f7a-8626-2773c4a60510',
    '9c702f14-23fe-401d-93bf-5d70765bb2d7',
    '2f947f0e-1e2b-4520-aa0d-ec90cb1d53cf',
    '470e9642-6bd4-4a2d-8790-8b15f85d6a2b',
]

for news_id in failing_ids[:3]:  # Check first 3
    article = db.query(RawNews).filter(RawNews.news_id == news_id).first()
    if article:
        print(f"\n{'='*70}")
        print(f"Title: {article.title[:100]}")
        print(f"Source: {article.source}")
        print(f"Text: {article.full_text[:300] if article.full_text else 'No text'}...")
        print(f"{'='*70}")

db.close()
