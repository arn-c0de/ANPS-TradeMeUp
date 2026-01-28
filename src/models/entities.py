"""Database models for entities and their relationships."""
from datetime import datetime
from sqlalchemy import Column, String, DateTime, ForeignKey, Float, Integer, Index
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import relationship
import uuid

from src.models.database import Base, utc_now
from src.models.types import GUID


class Entity(Base):
    """Model for entities (companies, sectors, people, etc.)."""

    __tablename__ = "entities"

    entity_id = Column(String(50), primary_key=True)  # Ticker or code
    entity_type = Column(String(20), nullable=False)  # company, sector, index, etc.
    entity_name = Column(String(200), nullable=False)
    metadata_ = Column("metadata", JSONB)  # Industry, market cap, etc. (renamed to avoid SQLAlchemy reserved name)
    created_at = Column(DateTime(timezone=True), nullable=False, default=utc_now)

    def __repr__(self):
        return f"<Entity(id={self.entity_id}, name={self.entity_name})>"


class NewsEntityMapping(Base):
    """Model for mapping news articles to entities."""

    __tablename__ = "news_entity_mapping"

    mapping_id = Column(GUID, primary_key=True, default=uuid.uuid4)
    news_id = Column(GUID, ForeignKey('raw_news.news_id'), nullable=False)
    entity_id = Column(String(50), ForeignKey('entities.entity_id'), nullable=False)
    exposure_type = Column(String(20))  # direct, indirect, supply_chain
    confidence = Column(Float)  # 0-1
    mention_count = Column(Integer, default=1)
    created_at = Column(DateTime(timezone=True), nullable=False, default=utc_now)

    # Relationships
    news = relationship("RawNews", backref="entity_mappings")
    entity = relationship("Entity", backref="news_mappings")

    # Indexes
    __table_args__ = (
        Index('idx_mapping_news', 'news_id'),
        Index('idx_mapping_entity', 'entity_id', 'created_at'),
    )

    def __repr__(self):
        return f"<NewsEntityMapping(news={self.news_id}, entity={self.entity_id})>"


class EntityRelationship(Base):
    """Model for relationships between entities (supply chain, competition, etc.)."""

    __tablename__ = "entity_relationships"

    relationship_id = Column(GUID, primary_key=True, default=uuid.uuid4)
    entity_from = Column(String(50), ForeignKey('entities.entity_id'), nullable=False)
    entity_to = Column(String(50), ForeignKey('entities.entity_id'), nullable=False)
    relationship_type = Column(String(50), nullable=False)  # supplies, competes_with, etc.
    strength = Column(Float)  # 0-1
    metadata_ = Column("metadata", JSONB)  # Renamed to avoid SQLAlchemy reserved name
    created_at = Column(DateTime(timezone=True), nullable=False, default=utc_now)

    # Relationships
    from_entity = relationship("Entity", foreign_keys=[entity_from])
    to_entity = relationship("Entity", foreign_keys=[entity_to])

    def __repr__(self):
        return f"<EntityRelationship({self.entity_from} -> {self.entity_to}: {self.relationship_type})>"
