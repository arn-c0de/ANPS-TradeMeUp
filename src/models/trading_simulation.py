"""Database model for trading simulation results."""
import uuid
from datetime import datetime

from sqlalchemy import Column, DateTime, Float, ForeignKey, Index, String
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import relationship

from src.models.database import Base, utc_now
from src.models.types import GUID


class TradingSimulation(Base):
    """Model for storing trading simulation outcomes."""

    __tablename__ = "trading_simulations"
    __table_args__ = {'extend_existing': True}

    simulation_id = Column(GUID, primary_key=True, default=uuid.uuid4)
    prediction_id = Column(GUID, ForeignKey("predictions.prediction_id"), nullable=False)
    entity_id = Column(String(50), ForeignKey("entities.entity_id"), nullable=False)
    horizon = Column(String(10), nullable=False)
    decision = Column(String(10), nullable=False)  # buy, sell, hold
    expected_return_pct = Column(Float)
    actual_return_pct = Column(Float)
    divergence_pct = Column(Float)
    risk_score = Column(Float)
    confidence = Column(Float)
    calibrated_confidence = Column(Float)

    # Cost metrics
    transaction_cost_bps = Column(Float)
    overnight_cost_bps = Column(Float)  # NEW: Overnight financing costs
    borrow_cost_bps = Column(Float)  # NEW: Short-selling borrow costs
    cost_breakdown = Column(JSONB)

    # Position metrics
    position_size_pct = Column(Float)  # NEW: Position size as % of portfolio
    position_value_usd = Column(Float)  # NEW: Position value in USD

    # Stop Loss & Take Profit
    stop_loss_price = Column(Float)  # Calculated stop loss price
    stop_loss_pct = Column(Float)  # Stop loss distance as percentage
    stop_loss_type = Column(String(20))  # atr_based, risk_adjusted, percentage
    trailing_stop_price = Column(Float)  # Trailing stop price (if applicable)
    take_profit_price = Column(Float)  # Target take profit price
    take_profit_pct = Column(Float)  # Take profit distance as percentage
    risk_reward_ratio = Column(Float)  # Risk/reward ratio
    exit_strategy = Column(JSONB)  # Detailed exit strategy metadata

    # Risk and metadata
    risk_breakdown = Column(JSONB)
    simulation_metadata = Column(JSONB)
    created_at = Column(DateTime(timezone=True), nullable=False, default=utc_now)

    prediction = relationship("Prediction", backref="simulations")
    entity = relationship("Entity")

    __table_args__ = (
        Index("idx_simulation_prediction", "prediction_id"),
        Index("idx_simulation_entity_time", "entity_id", "created_at"),
        Index("idx_simulation_decision", "decision", "created_at"),
        Index("idx_simulation_risk_score", "risk_score"),  # NEW: Index for risk-based queries
    )

    def __repr__(self):
        return (
            f"<TradingSimulation(prediction={self.prediction_id}, "
            f"decision={self.decision}, risk={self.risk_score})>"
        )
