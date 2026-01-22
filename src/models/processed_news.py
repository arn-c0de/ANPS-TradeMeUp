"""Database model for processed news with NLP analysis."""
from datetime import datetime
from sqlalchemy import Column, String, Text, Float, JSON, DateTime, ForeignKey, Index
from sqlalchemy.orm import relationship
import uuid

from src.models.database import Base
from src.models.types import GUID


class ProcessedNews(Base):
    """Model for storing NLP-processed news articles."""

    __tablename__ = "processed_news"

    news_id = Column(GUID, ForeignKey('raw_news.news_id'), primary_key=True)
    summary_short = Column(Text)  # 1 sentence
    summary_medium = Column(Text)  # 3-5 sentences
    key_facts = Column(JSON)  # List of extracted facts with confidence
    sentiment = Column(JSON)  # Overall and aspect-based sentiment
    event_type = Column(String(50))  # earnings, M&A, regulation, etc.
    event_subtype = Column(String(100))  # More specific classification
    confidence = Column(Float)  # Model confidence 0-1
    embedding = Column(JSON)  # 768-dim vector (stored as JSON for SQLite, pgvector in production)
    llm_metadata = Column(JSON)  # Model version, tokens, etc.
    processing_timestamp = Column(DateTime(timezone=True), nullable=False, default=datetime.utcnow)

    # Relationships
    news = relationship("RawNews", backref="processed")

    def __repr__(self):
        return f"<ProcessedNews(id={self.news_id}, event_type={self.event_type})>"
