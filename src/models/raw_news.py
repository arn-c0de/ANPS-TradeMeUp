"""Database model for raw news articles."""
import uuid

from sqlalchemy import Column, DateTime, Index, String, Text
from sqlalchemy.dialects.postgresql import JSONB

from src.models.database import Base, utc_now
from src.models.types import GUID


class RawNews(Base):
    """Model for storing raw news articles from various sources."""

    __tablename__ = "raw_news"

    news_id = Column(GUID, primary_key=True, default=uuid.uuid4)
    source = Column(String(100), nullable=False)
    source_url = Column(String(500))
    published_at = Column(DateTime(timezone=True), nullable=False)
    fetched_at = Column(DateTime(timezone=True), nullable=False, default=utc_now)
    title = Column(Text, nullable=False)
    full_text = Column(Text, nullable=False)
    url = Column(Text, unique=True, nullable=False)
    language = Column(String(10))
    content_hash = Column(String(64), unique=True)  # SHA-256 hash
    author = Column(String(200))
    metadata_ = Column("metadata", JSONB)  # Renamed to avoid SQLAlchemy reserved name
    created_at = Column(DateTime(timezone=True), nullable=False, default=utc_now)

    # Indexes for performance
    __table_args__ = (
        Index('idx_raw_news_published', 'published_at'),
        Index('idx_raw_news_source', 'source', 'published_at'),
        Index('idx_raw_news_hash', 'content_hash'),
        Index('idx_raw_news_fetched', 'fetched_at'),  # For date range filters in GUI
    )

    def __repr__(self):
        return f"<RawNews(id={self.news_id}, source={self.source}, title={self.title[:50]})>"
