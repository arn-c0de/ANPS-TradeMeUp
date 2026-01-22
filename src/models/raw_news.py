"""Database model for raw news articles."""
from datetime import datetime
from sqlalchemy import Column, String, Text, DateTime, JSON, Index
import uuid

from src.models.database import Base
from src.models.types import GUID


class RawNews(Base):
    """Model for storing raw news articles from various sources."""

    __tablename__ = "raw_news"

    news_id = Column(GUID, primary_key=True, default=uuid.uuid4)
    source = Column(String(100), nullable=False)
    source_url = Column(String(500))
    published_at = Column(DateTime(timezone=True), nullable=False)
    fetched_at = Column(DateTime(timezone=True), nullable=False, default=datetime.utcnow)
    title = Column(Text, nullable=False)
    full_text = Column(Text, nullable=False)
    url = Column(Text, unique=True, nullable=False)
    language = Column(String(10))
    content_hash = Column(String(64), unique=True)  # SHA-256 hash
    author = Column(String(200))
    metadata_ = Column("metadata", JSON)  # Renamed to avoid SQLAlchemy reserved name
    created_at = Column(DateTime(timezone=True), nullable=False, default=datetime.utcnow)

    # Indexes for performance
    __table_args__ = (
        Index('idx_raw_news_published', 'published_at'),
        Index('idx_raw_news_source', 'source', 'published_at'),
        Index('idx_raw_news_hash', 'content_hash'),
    )

    def __repr__(self):
        return f"<RawNews(id={self.news_id}, source={self.source}, title={self.title[:50]})>"
