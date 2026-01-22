"""API endpoints for entities."""
from typing import List
from fastapi import APIRouter, Depends, Query, HTTPException
from sqlalchemy.orm import Session
from pydantic import BaseModel

from src.models.database import get_db
from src.models.entities import Entity, NewsEntityMapping

router = APIRouter(prefix="/entities", tags=["entities"])


class EntityResponse(BaseModel):
    """Response model for entities."""
    entity_id: str
    entity_type: str
    entity_name: str
    metadata: dict | None = None

    class Config:
        from_attributes = True
        populate_by_name = True


@router.get("/", response_model=List[EntityResponse])
def list_entities(
    entity_type: str = Query(None, description="Filter by type (company, sector, etc.)"),
    limit: int = Query(100, le=500, description="Maximum results"),
    db: Session = Depends(get_db)
):
    """
    List all entities (companies, sectors, etc.).

    - **entity_type**: Filter by entity type (company, sector, index)
    - **limit**: Maximum number of results
    """
    query = db.query(Entity)

    if entity_type:
        query = query.filter(Entity.entity_type == entity_type)

    entities = query.limit(limit).all()

    return [EntityResponse.from_orm(e) for e in entities]


@router.get("/{entity_id}")
def get_entity_detail(
    entity_id: str,
    db: Session = Depends(get_db)
):
    """Get detailed information for a specific entity."""
    entity = db.query(Entity).filter(Entity.entity_id == entity_id).first()

    if not entity:
        raise HTTPException(status_code=404, detail="Entity not found")

    # Count news mentions
    mention_count = db.query(NewsEntityMapping).filter(
        NewsEntityMapping.entity_id == entity_id
    ).count()

    # Get recent news
    from src.models.raw_news import RawNews
    recent_news = db.query(RawNews).join(
        NewsEntityMapping,
        RawNews.news_id == NewsEntityMapping.news_id
    ).filter(
        NewsEntityMapping.entity_id == entity_id
    ).order_by(
        RawNews.published_at.desc()
    ).limit(10).all()

    return {
        "entity_id": entity.entity_id,
        "entity_type": entity.entity_type,
        "entity_name": entity.entity_name,
        "metadata": entity.metadata_,
        "total_news_mentions": mention_count,
        "recent_news": [
            {
                "news_id": str(n.news_id),
                "title": n.title,
                "published_at": n.published_at
            }
            for n in recent_news
        ]
    }


@router.get("/statistics/summary")
def get_entity_statistics(db: Session = Depends(get_db)):
    """Get entity statistics."""
    from sqlalchemy import func

    total = db.query(Entity).count()

    by_type = db.query(
        Entity.entity_type,
        func.count(Entity.entity_id).label('count')
    ).group_by(Entity.entity_type).all()

    # Top mentioned entities
    top_entities = db.query(
        NewsEntityMapping.entity_id,
        Entity.entity_name,
        func.count(NewsEntityMapping.mapping_id).label('mentions')
    ).join(
        Entity,
        NewsEntityMapping.entity_id == Entity.entity_id
    ).group_by(
        NewsEntityMapping.entity_id,
        Entity.entity_name
    ).order_by(
        func.count(NewsEntityMapping.mapping_id).desc()
    ).limit(10).all()

    return {
        "total_entities": total,
        "by_type": {et: count for et, count in by_type},
        "top_mentioned": [
            {"entity_id": eid, "name": name, "mentions": mentions}
            for eid, name, mentions in top_entities
        ]
    }
