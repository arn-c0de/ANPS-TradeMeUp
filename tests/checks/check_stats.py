#!/usr/bin/env python3
"""Quick stats checker for database"""
import sys
from pathlib import Path

from sqlalchemy import func, select

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
print(f"RawNews Total:              {db.scalar(select(func.count()).select_from(RawNews))}")
print(f"RawNews with quality_score: {db.scalar(select(func.count()).select_from(RawNews).where(RawNews.quality_score.any()))}")
print(f"ProcessedNews:              {db.scalar(select(func.count()).select_from(ProcessedNews))}")
print(f"Entities:                   {db.scalar(select(func.count()).select_from(Entity))}")
print(f"EntityMappings:             {db.scalar(select(func.count()).select_from(NewsEntityMapping))}")
print(f"SurpriseScores:             {db.scalar(select(func.count()).select_from(SurpriseScore))}")
print(f"ImpactScores:               {db.scalar(select(func.count()).select_from(ImpactScore))}")
print(f"FactVerifications:          {db.scalar(select(func.count()).select_from(FactVerification))}")
print(f"Predictions:                {db.scalar(select(func.count()).select_from(Prediction))}")
print("=" * 60)

# Check what's blocking the pipeline
unprocessed = db.scalar(select(func.count()).select_from(select(RawNews).where(
    RawNews.quality_score.any()
).outerjoin(
    ProcessedNews, RawNews.news_id == ProcessedNews.news_id
).where(ProcessedNews.news_id.is_(None)).subquery()))

print(f"\nArticles needing NLP processing: {unprocessed}")

# Check ProcessedNews without entities
processed_without_entities = db.scalar(select(func.count()).select_from(select(ProcessedNews).outerjoin(
    NewsEntityMapping, ProcessedNews.news_id == NewsEntityMapping.news_id
).where(NewsEntityMapping.news_id.is_(None)).subquery()))

print(f"ProcessedNews without entities: {processed_without_entities}")

# Check ProcessedNews without fact verification
processed_without_facts = db.scalar(select(func.count()).select_from(select(ProcessedNews).outerjoin(
    FactVerification, ProcessedNews.news_id == FactVerification.news_id
).where(FactVerification.news_id.is_(None)).subquery()))

print(f"ProcessedNews without fact checks: {processed_without_facts}")

db.close()
