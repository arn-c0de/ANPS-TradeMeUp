"""Database models for chart overlays (brackets and breaks)."""
from datetime import datetime
from sqlalchemy import Column, String, Float, Boolean, DateTime, Index
import uuid

from src.models.database import Base
from src.models.types import GUID


class ChartOverlay(Base):
    """Model for chart overlay lines (brackets/breaks)."""

    __tablename__ = "chart_overlays"

    overlay_id = Column(GUID, primary_key=True, default=uuid.uuid4)
    symbol = Column(String(20), nullable=False, index=True)  # Stock ticker
    timeframe = Column(String(20), nullable=False)  # e.g., "1mo", "1d_1m"
    group = Column(String(20), nullable=False)  # "brackets" or "breaks"
    price = Column(Float, nullable=False)
    name = Column(String(100))  # Optional label/name
    color = Column(String(20), nullable=False)  # Hex color code
    visible = Column(Boolean, default=True)
    created_at = Column(DateTime(timezone=True), nullable=False, default=datetime.utcnow)
    updated_at = Column(DateTime(timezone=True), nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Composite index for fast lookups
    __table_args__ = (
        Index('idx_symbol_timeframe', 'symbol', 'timeframe'),
    )

    def __repr__(self):
        return f"<ChartOverlay(symbol={self.symbol}, group={self.group}, price={self.price}, name={self.name})>"

    def to_dict(self):
        """Convert to dictionary format used by frontend."""
        return {
            'id': str(self.overlay_id),
            'price': self.price,
            'name': self.name or '',
            'color': self.color,
            'visible': self.visible
        }
