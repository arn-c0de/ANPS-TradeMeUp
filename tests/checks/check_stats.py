#!/usr/bin/env python3
"""Quick stats checker for database"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from src.models.analysis import FactVerification, ImpactScore, SurpriseScore
from src.models.database import SessionLocal
from src.models.entities import Entity, NewsEntityMapping
from src.models.predictions import Prediction
from src.models.processed_news import ProcessedNews
from src.models.raw_news import RawNews

db = SessionLocal()

print("=" * 60)
print("DATABASE STATISTICS")
print("=" * 60)
print(f"RawNews Total:              {db.query(RawNews).count()}")
print(f"RawNews with quality_score: {db.query(RawNews).filter(RawNews.quality_score.is_not(None)).count()}")
print(f"ProcessedNews:              {db.query(ProcessedNews).count()}")
print(f"Entities:                   {db.query(Entity).count()}")
print(f"EntityMappings:             {db.query(NewsEntityMapping).count()}")
print(f"SurpriseScores:             {db.query(SurpriseScore).count()}")
print(f"ImpactScores:               {db.query(ImpactScore).count()}")
print(f"FactVerifications:          {db.query(FactVerification).count()}")
print(f"Predictions:                {db.query(Prediction).count()}")
print("=" * 60)

# Check what's blocking the pipeline
unprocessed = db.query(RawNews).filter(
    RawNews.quality_score.is_not(None)
).outerjoin(
    ProcessedNews, RawNews.news_id == ProcessedNews.news_id
).filter(ProcessedNews.news_id.is_(None)).count()

print(f"\nArticles needing NLP processing: {unprocessed}")

# Check ProcessedNews without entities
processed_without_entities = db.query(ProcessedNews).outerjoin(
    NewsEntityMapping, ProcessedNews.news_id == NewsEntityMapping.news_id
).filter(NewsEntityMapping.news_id.is_(None)).count()

print(f"ProcessedNews without entities: {processed_without_entities}")

# Check ProcessedNews without fact verification
processed_without_facts = db.query(ProcessedNews).outerjoin(
    FactVerification, ProcessedNews.news_id == FactVerification.news_id
).filter(FactVerification.news_id.is_(None)).count()

print(f"ProcessedNews without fact checks: {processed_without_facts}")

db.close()
