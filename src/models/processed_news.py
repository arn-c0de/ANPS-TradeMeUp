"""Database model for processed news with NLP analysis."""
from datetime import datetime
from sqlalchemy import Column, String, Text, Float, DateTime, ForeignKey, Index
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import relationship, deferred
import uuid

from src.models.database import Base, utc_now
from src.models.types import GUID

# pgvector support (optional)
try:
    from pgvector.sqlalchemy import Vector
    HAS_PGVECTOR = True
except ImportError:
    HAS_PGVECTOR = False


class ProcessedNews(Base):
    """Model for storing NLP-processed news articles."""

    __tablename__ = "processed_news"

    news_id = Column(GUID, ForeignKey('raw_news.news_id'), primary_key=True)
    summary_short = Column(Text)  # 1 sentence
    summary_medium = Column(Text)  # 3-5 sentences
    key_facts = Column(JSONB)  # List of extracted facts with confidence
    sentiment = Column(JSONB)  # Overall and aspect-based sentiment
    event_type = Column(String(50))  # earnings, M&A, regulation, etc.
    event_subtype = Column(String(100))  # More specific classification
    confidence = Column(Float)  # Model confidence 0-1
    # Use pgvector if available, otherwise JSONB
    # Deferred loading to avoid loading large embeddings unless explicitly needed
    embedding = deferred(Column(Vector(768) if HAS_PGVECTOR else JSONB))  # 768-dim vector
    llm_metadata = Column(JSONB)  # Model version, tokens, etc.
    processing_timestamp = Column(DateTime(timezone=True), nullable=False, default=utc_now)

    # Relationships
    news = relationship("RawNews", backref="processed")

    def __repr__(self):
        return f"<ProcessedNews(id={self.news_id}, event_type={self.event_type})>"
