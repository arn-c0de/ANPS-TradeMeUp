"""Database model for trading simulation results."""
from datetime import datetime
import uuid
from sqlalchemy import Column, String, Float, JSON, DateTime, ForeignKey, Index
from sqlalchemy.orm import relationship

from src.models.database import Base
from src.models.types import GUID


class TradingSimulation(Base):
    """Model for storing trading simulation outcomes."""

    __tablename__ = "trading_simulations"

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
    transaction_cost_bps = Column(Float)
    cost_breakdown = Column(JSON)
    risk_breakdown = Column(JSON)
    simulation_metadata = Column(JSON)
    created_at = Column(DateTime(timezone=True), nullable=False, default=datetime.utcnow)

    prediction = relationship("Prediction", backref="simulations")
    entity = relationship("Entity")

    __table_args__ = (
        Index("idx_simulation_prediction", "prediction_id"),
        Index("idx_simulation_entity_time", "entity_id", "created_at"),
        Index("idx_simulation_decision", "decision", "created_at"),
    )

    def __repr__(self):
        return (
            f"<TradingSimulation(prediction={self.prediction_id}, "
            f"decision={self.decision}, risk={self.risk_score})>"
        )
