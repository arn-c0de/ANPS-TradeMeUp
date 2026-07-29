"""Database model for data quality scores."""

from sqlalchemy import Column, DateTime, Float, ForeignKey
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import relationship

from src.models.database import Base, utc_now
from src.models.types import GUID


class DataQualityScore(Base):
    """Model for data quality assessment of news articles."""

    __tablename__ = "data_quality_scores"

    news_id = Column(GUID, ForeignKey('raw_news.news_id'), primary_key=True)
    quality_score = Column(Float, nullable=False)  # 0-1 scale
    duplicate_of = Column(GUID, ForeignKey('raw_news.news_id'), nullable=True)
    validation_flags = Column(JSONB, nullable=False)  # Dict of validation results
    quality_issues = Column(JSONB, default=list)  # List of issues found
    source_reliability_score = Column(Float)  # 0-1 scale
    created_at = Column(DateTime(timezone=True), nullable=False, default=utc_now)

    # Relationships
    news = relationship("RawNews", foreign_keys=[news_id], backref="quality_score")
    duplicate_source = relationship("RawNews", foreign_keys=[duplicate_of])

    def __repr__(self):
        return f"<DataQualityScore(news_id={self.news_id}, score={self.quality_score})>"
