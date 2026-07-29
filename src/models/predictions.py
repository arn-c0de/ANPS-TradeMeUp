"""Database models for predictions and outcomes."""
import uuid

from sqlalchemy import (
    Boolean,
    Column,
    DateTime,
    Float,
    ForeignKey,
    Index,
    Integer,
    PrimaryKeyConstraint,
    String,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import relationship

from src.models.database import Base, utc_now
from src.models.types import GUID


class Prediction(Base):
    """Model for market predictions."""

    __tablename__ = "predictions"

    prediction_id = Column(GUID, primary_key=True, default=uuid.uuid4)
    entity_id = Column(String(50), ForeignKey('entities.entity_id'), nullable=False)
    timestamp = Column(DateTime(timezone=True), nullable=False)
    horizon = Column(String(10), nullable=False)  # 1d, 5d, 20d
    direction_probabilities = Column(JSONB, nullable=False)  # {up, flat, down}
    expected_return = Column(JSONB, nullable=False)  # {mean, median, p25, p75, p95}
    confidence = Column(Float, nullable=False)
    calibrated_confidence = Column(Float)
    model_contributions = Column(JSONB)
    key_drivers = Column(JSONB)
    model_version = Column(String(50), nullable=False)
    related_news_ids = Column(JSONB)  # Array of news UUIDs
    created_at = Column(DateTime(timezone=True), nullable=False, default=utc_now)

    # Relationships
    entity = relationship("Entity", backref="predictions")

    # Indexes
    __table_args__ = (
        Index('idx_predictions_entity_time', 'entity_id', 'timestamp'),
        Index('idx_predictions_created', 'created_at'),
        Index('idx_predictions_horizon', 'horizon', 'created_at'),  # For filtering by horizon + date
    )

    # Derived, read-only views of the JSONB payloads. Several agents already
    # read `prediction.predicted_direction` / `.predicted_return` / `.model_id`
    # as if they were columns; they are not, so those paths raised
    # AttributeError on the first row. Deriving them here keeps every consumer
    # on one interpretation of the stored JSON.

    @property
    def predicted_direction(self) -> str:
        """Most likely direction ('up' / 'down' / 'flat')."""
        from src.utils.prediction_math import get_predicted_direction
        return get_predicted_direction(self)

    @property
    def predicted_return(self) -> float:
        """Expected return as a percentage (2.0 means +2%)."""
        from src.utils.prediction_math import get_expected_return_pct
        return get_expected_return_pct(self)

    # Deliberately no `model_id` alias: the column is `model_version`, and a
    # property would only work on instances. `Prediction.model_id == x` inside
    # a query filter would silently compare a property object instead of
    # emitting SQL. Call sites use model_version directly.

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
    created_at = Column(DateTime(timezone=True), nullable=False, default=utc_now)

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
    metrics = Column(JSONB, nullable=False)  # accuracy, sharpe, drawdown, etc.
    regime_breakdown = Column(JSONB)
    error_analysis = Column(JSONB)
    created_at = Column(DateTime(timezone=True), nullable=False, default=utc_now)

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
    metadata_ = Column("metadata", JSONB)  # Renamed to avoid SQLAlchemy reserved name

    # Composite primary key
    __table_args__ = (
        PrimaryKeyConstraint('ticker', 'timestamp', name='pk_market_data'),
        Index('idx_market_data_ticker_time', 'ticker', 'timestamp'),
    )

    # In production with TimescaleDB, this would be converted to hypertable

    def __repr__(self):
        return f"<MarketData(ticker={self.ticker}, timestamp={self.timestamp}, close={self.close})>"
