"""API endpoints for news."""
from datetime import datetime
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, ConfigDict
from sqlalchemy.orm import Session

from src.models.data_quality import DataQualityScore
from src.models.database import get_db
from src.models.processed_news import ProcessedNews
from src.models.raw_news import RawNews

router = APIRouter(prefix="/news", tags=["news"])


class NewsResponse(BaseModel):
    """Response model for news."""
    news_id: str
    source: str
    title: str
    published_at: datetime
    url: str
    quality_score: float | None = None
    event_type: str | None = None
    sentiment: dict | None = None

    model_config = ConfigDict(from_attributes=True)


@router.get("/", response_model=list[NewsResponse])
def list_news(
    source: str | None = Query(None, description="Filter by source"),
    event_type: str | None = Query(None, description="Filter by event type"),
    min_quality: float = Query(0.6, ge=0.0, le=1.0, description="Minimum quality score"),
    start_date: datetime | None = Query(None, description="Start date"),
    end_date: datetime | None = Query(None, description="End date"),
    limit: int = Query(50, le=200, description="Maximum results"),
    db: Session = Depends(get_db)
):
    """
    List news articles with optional filters.

    - **source**: Filter by news source
    - **event_type**: Filter by event type (earnings, m_and_a, etc.)
    - **min_quality**: Minimum quality score
    - **start_date**: Start date for filtering
    - **end_date**: End date for filtering
    - **limit**: Maximum number of results
    """
    query = db.query(RawNews).join(
        DataQualityScore,
        RawNews.news_id == DataQualityScore.news_id,
        isouter=True
    ).outerjoin(
        ProcessedNews,
        RawNews.news_id == ProcessedNews.news_id
    )

    # Apply filters
    if source:
        query = query.filter(RawNews.source.contains(source))

    if event_type:
        query = query.filter(ProcessedNews.event_type == event_type)

    if min_quality > 0:
        query = query.filter(DataQualityScore.quality_score >= min_quality)

    if start_date:
        query = query.filter(RawNews.published_at >= start_date)

    if end_date:
        query = query.filter(RawNews.published_at <= end_date)

    # Order by date desc and limit
    news_items = query.order_by(RawNews.published_at.desc()).limit(limit).all()

    # Build response
    results = []
    for news in news_items:
        quality = db.query(DataQualityScore).filter(
            DataQualityScore.news_id == news.news_id
        ).first()

        processed = db.query(ProcessedNews).filter(
            ProcessedNews.news_id == news.news_id
        ).first()

        result = NewsResponse(
            news_id=str(news.news_id),
            source=news.source,
            title=news.title,
            published_at=news.published_at,
            url=news.url,
            quality_score=quality.quality_score if quality else None,
            event_type=processed.event_type if processed else None,
            sentiment=processed.sentiment if processed else None
        )
        results.append(result)

    return results


@router.get("/{news_id}")
def get_news_detail(
    news_id: str,
    db: Session = Depends(get_db)
):
    """Get detailed information for a specific news article."""
    news = db.query(RawNews).filter(RawNews.news_id == news_id).first()

    if not news:
        raise HTTPException(status_code=404, detail="News article not found")

    # Get related data
    quality = db.query(DataQualityScore).filter(
        DataQualityScore.news_id == news_id
    ).first()

    processed = db.query(ProcessedNews).filter(
        ProcessedNews.news_id == news_id
    ).first()

    return {
        "news_id": str(news.news_id),
        "source": news.source,
        "title": news.title,
        "full_text": news.full_text,
        "url": news.url,
        "published_at": news.published_at,
        "fetched_at": news.fetched_at,
        "author": news.author,
        "quality_score": quality.quality_score if quality else None,
        "event_type": processed.event_type if processed else None,
        "event_subtype": processed.event_subtype if processed else None,
        "sentiment": processed.sentiment if processed else None,
        "summary_short": processed.summary_short if processed else None,
        "summary_medium": processed.summary_medium if processed else None,
        "key_facts": processed.key_facts if processed else None
    }
