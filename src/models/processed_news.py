"""Database model for processed news with NLP analysis."""
from sqlalchemy import Column, DateTime, Float, ForeignKey, String, Text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import deferred, relationship

from src.models.database import Base, utc_now
from src.models.types import GUID


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
    # Embeddings are currently stored as JSON arrays to match the live schema.
    # This keeps Docker/bootstrap installs stable across environments.
    embedding = deferred(Column(JSONB))
    llm_metadata = Column(JSONB)  # Model version, tokens, etc.
    processing_timestamp = Column(DateTime(timezone=True), nullable=False, default=utc_now)

    # Relationships
    news = relationship("RawNews", backref="processed")

    def __repr__(self):
        return f"<ProcessedNews(id={self.news_id}, event_type={self.event_type})>"
