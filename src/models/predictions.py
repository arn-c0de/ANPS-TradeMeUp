"""Database models for predictions and outcomes."""
from datetime import datetime
from sqlalchemy import Column, String, Float, Boolean, JSON, DateTime, ForeignKey, Index, Integer, PrimaryKeyConstraint
from sqlalchemy.orm import relationship
import uuid

from src.models.database import Base
from src.models.types import GUID


class Prediction(Base):
    """Model for market predictions."""

    __tablename__ = "predictions"

    prediction_id = Column(GUID, primary_key=True, default=uuid.uuid4)
    entity_id = Column(String(50), ForeignKey('entities.entity_id'), nullable=False)
    timestamp = Column(DateTime(timezone=True), nullable=False)
    horizon = Column(String(10), nullable=False)  # 1d, 5d, 20d
    direction_probabilities = Column(JSON, nullable=False)  # {up, flat, down}
    expected_return = Column(JSON, nullable=False)  # {mean, median, p25, p75, p95}
    confidence = Column(Float, nullable=False)
    calibrated_confidence = Column(Float)
    model_contributions = Column(JSON)
    key_drivers = Column(JSON)
    model_version = Column(String(50), nullable=False)
    related_news_ids = Column(JSON)  # Array of news UUIDs (stored as JSON for SQLite compat)
    created_at = Column(DateTime(timezone=True), nullable=False, default=datetime.utcnow)

    # Relationships
    entity = relationship("Entity", backref="predictions")

    # Indexes
    __table_args__ = (
        Index('idx_predictions_entity_time', 'entity_id', 'timestamp'),
        Index('idx_predictions_created', 'created_at'),
    )

    def __repr__(self):
        return f"<Prediction(id={self.prediction_id}, entity={self.entity_id}, horizon={self.horizon})>"


class PredictionOutcome(Base):
    """Model for storing actual prediction outcomes."""

    __tablename__ = "prediction_outcomes"

    outcome_id = Column(GUID, primary_key=True, default=uuid.uuid4)
    prediction_id = Column(GUID, ForeignKey('predictions.prediction_id'), nullable=False)
    actual_return = Column(Float)
    error = Column(Float)
    direction_correct = Column(Boolean)
    within_confidence_interval = Column(Boolean)
    sharpe_contribution = Column(Float)
    evaluation_timestamp = Column(DateTime(timezone=True), nullable=False)
    created_at = Column(DateTime(timezone=True), nullable=False, default=datetime.utcnow)

    # Relationships
    prediction = relationship("Prediction", backref="outcome")

    # Indexes
    __table_args__ = (
        Index('idx_outcomes_prediction', 'prediction_id'),
    )

    def __repr__(self):
        return f"<PredictionOutcome(prediction={self.prediction_id}, correct={self.direction_correct})>"


class BacktestResult(Base):
    """Model for storing backtest results."""

    __tablename__ = "backtest_results"

    backtest_id = Column(GUID, primary_key=True, default=uuid.uuid4)
    model_version = Column(String(50), nullable=False)
    evaluation_period_start = Column(DateTime(timezone=True), nullable=False)
    evaluation_period_end = Column(DateTime(timezone=True), nullable=False)
    metrics = Column(JSON, nullable=False)  # accuracy, sharpe, drawdown, etc.
    regime_breakdown = Column(JSON)
    error_analysis = Column(JSON)
    created_at = Column(DateTime(timezone=True), nullable=False, default=datetime.utcnow)

    def __repr__(self):
        return f"<BacktestResult(model={self.model_version}, period={self.evaluation_period_start} to {self.evaluation_period_end})>"


class MarketData(Base):
    """Model for market data (TimescaleDB hypertable in production)."""

    __tablename__ = "market_data"

    ticker = Column(String(50), nullable=False)
    timestamp = Column(DateTime(timezone=True), nullable=False)
    open = Column(Float)
    high = Column(Float)
    low = Column(Float)
    close = Column(Float)
    volume = Column(Integer)
    vwap = Column(Float)
    volatility_1d = Column(Float)
    metadata_ = Column("metadata", JSON)  # Renamed to avoid SQLAlchemy reserved name

    # Composite primary key
    __table_args__ = (
        PrimaryKeyConstraint('ticker', 'timestamp', name='pk_market_data'),
        Index('idx_market_data_ticker_time', 'ticker', 'timestamp'),
    )

    # In production with TimescaleDB, this would be converted to hypertable

    def __repr__(self):
        return f"<MarketData(ticker={self.ticker}, timestamp={self.timestamp}, close={self.close})>"
