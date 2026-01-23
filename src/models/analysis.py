"""Database models for analysis results."""
from datetime import datetime
from sqlalchemy import Column, String, Float, JSON, DateTime, ForeignKey, Index, Integer
from sqlalchemy.orm import relationship
import uuid

from src.models.database import Base
from src.models.types import GUID


class ImpactScore(Base):
    """Model for impact scores per news-entity pair."""

    __tablename__ = "impact_scores"

    score_id = Column(GUID, primary_key=True, default=uuid.uuid4)
    news_id = Column(GUID, ForeignKey('raw_news.news_id'), nullable=False)
    entity_id = Column(String(50), ForeignKey('entities.entity_id'), nullable=False)
    impact_score = Column(Float, nullable=False)  # 0-1 scale
    impact_breakdown = Column(JSON)  # Detailed component scores
    confidence = Column(Float)
    time_horizon = Column(String(20))  # short_term, medium_term, long_term
    expected_volatility_impact = Column(Float)
    created_at = Column(DateTime(timezone=True), nullable=False, default=datetime.utcnow)

    # Relationships
    news = relationship("RawNews", backref="impact_scores")
    entity = relationship("Entity", backref="impact_scores")

    # Indexes
    __table_args__ = (
        Index('idx_impact_entity_time', 'entity_id', 'created_at'),
    )

    def __repr__(self):
        return f"<ImpactScore(news={self.news_id}, entity={self.entity_id}, score={self.impact_score})>"


class SurpriseScore(Base):
    """Model for surprise quantification."""

    __tablename__ = "surprise_scores"

    surprise_id = Column(GUID, primary_key=True, default=uuid.uuid4)
    news_id = Column(GUID, ForeignKey('raw_news.news_id'), nullable=False)
    metric = Column(String(100), nullable=False)  # earnings_per_share, revenue, etc.
    actual = Column(Float)
    consensus = Column(Float)
    surprise_raw = Column(Float)
    surprise_normalized = Column(Float)  # in std devs
    surprise_percentile = Column(Float)
    market_priced_in = Column(Float)
    true_surprise = Column(Float)
    expected_reaction = Column(String(50))
    created_at = Column(DateTime(timezone=True), nullable=False, default=datetime.utcnow)

    # Relationships
    news = relationship("RawNews", backref="surprise_scores")

    def __repr__(self):
        return f"<SurpriseScore(news={self.news_id}, metric={self.metric}, surprise={self.surprise_normalized})>"


class MarketRegime(Base):
    """Model for market regime state."""

    __tablename__ = "market_regimes"

    regime_id = Column(GUID, primary_key=True, default=uuid.uuid4)
    timestamp = Column(DateTime(timezone=True), nullable=False)
    regime = Column(JSON, nullable=False)  # {volatility, trend, risk_appetite, etc.}
    regime_probabilities = Column(JSON)
    regime_metadata = Column(JSON)  # VIX, breadth, etc.
    created_at = Column(DateTime(timezone=True), nullable=False, default=datetime.utcnow)

    # Indexes
    __table_args__ = (
        Index('idx_regime_time', 'timestamp'),
    )

    def __repr__(self):
        return f"<MarketRegime(timestamp={self.timestamp}, regime={self.regime})>"


class SignalDecayModel(Base):
    """Model for signal decay parameters."""

    __tablename__ = "signal_decay_models"

    news_id = Column(GUID, ForeignKey('raw_news.news_id'), primary_key=True)
    initial_impact = Column(Float)
    decay_rate = Column(Float)  # per day
    half_life_days = Column(Float)
    effective_window_days = Column(Integer)
    model_type = Column(String(50))  # exponential, power_law, etc.
    created_at = Column(DateTime(timezone=True), nullable=False, default=datetime.utcnow)

    # Relationships
    news = relationship("RawNews", backref="signal_decay")

    def __repr__(self):
        return f"<SignalDecayModel(news={self.news_id}, half_life={self.half_life_days})>"


class FactVerification(Base):
    """Model for fact verification results."""

    __tablename__ = "fact_verifications"

    verification_id = Column(GUID, primary_key=True, default=uuid.uuid4)
    news_id = Column(GUID, ForeignKey('raw_news.news_id'), nullable=False)
    claims_verified = Column(JSON, nullable=False)  # List of verified claims
    contradictions_found = Column(Integer, default=0)  # Boolean as int
    contradiction_details = Column(JSON)  # Details of contradictions
    credibility_score = Column(Float, nullable=False)  # 0-1 scale
    verification_method = Column(String(50))  # llm_cross_check, manual, etc.
    verified_at = Column(DateTime(timezone=True), nullable=False)
    verification_notes = Column(String(1000))

    # Relationships
    news = relationship("RawNews", backref="fact_verifications")

    # Indexes
    __table_args__ = (
        Index('idx_fact_verification_news', 'news_id'),
    )

    def __repr__(self):
        return f"<FactVerification(news={self.news_id}, credibility={self.credibility_score})>"
