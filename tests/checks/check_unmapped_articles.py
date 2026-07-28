"""Check how many articles don't have entity mappings"""

from sqlalchemy import exists, func

from src.models.database import SessionLocal
from src.models.entities import NewsEntityMapping
from src.models.processed_news import ProcessedNews
from src.models.raw_news import RawNews

db = SessionLocal()

# Total processed articles
total_processed = db.query(func.count(ProcessedNews.news_id)).scalar()

# Articles WITH mappings
with_mappings = db.query(func.count(func.distinct(NewsEntityMapping.news_id))).scalar()

# Articles WITHOUT mappings (using NOT EXISTS like the fixed query)
without_mappings = db.query(func.count(RawNews.news_id)).join(
    ProcessedNews,
    RawNews.news_id == ProcessedNews.news_id
).filter(
    ~exists().where(NewsEntityMapping.news_id == RawNews.news_id)
).scalar()

print("📊 Entity Mapping Coverage:")
print(f"   Total Processed Articles: {total_processed}")
print(f"   With Mappings: {with_mappings} ({with_mappings/total_processed*100:.1f}%)")
print(f"   Without Mappings: {without_mappings} ({without_mappings/total_processed*100:.1f}%)")
print("   Target: ~1400 with mappings (70%)")

db.close()
