"""Database model for market data (OHLCV)."""
from datetime import datetime
from sqlalchemy import Column, String, Float, DateTime, Index, Integer
from sqlalchemy.orm import relationship
import uuid

from src.models.database import Base
from src.models.types import GUID


class MarketData(Base):
    """Model for historical market data (OHLCV)."""

    __tablename__ = "market_data"

    data_id = Column(GUID, primary_key=True, default=uuid.uuid4)
    entity_id = Column(String(50), nullable=False)  # Ticker symbol
    timestamp = Column(DateTime(timezone=True), nullable=False)
    open = Column(Float, nullable=False)
    high = Column(Float, nullable=False)
    low = Column(Float, nullable=False)
    close = Column(Float, nullable=False)
    volume = Column(Integer, nullable=False)
    adjusted_close = Column(Float)
    source = Column(String(50), default='yfinance')
    created_at = Column(DateTime(timezone=True), nullable=False, default=datetime.utcnow)

    # Indexes for fast queries
    __table_args__ = (
        Index('idx_market_data_entity_time', 'entity_id', 'timestamp'),
    )

    def __repr__(self):
        return f"<MarketData(entity={self.entity_id}, time={self.timestamp}, close={self.close})>"
