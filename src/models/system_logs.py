"""SQLAlchemy model for centralised server-side log storage."""
from sqlalchemy import BigInteger, Column, DateTime, Index, String, Text
from sqlalchemy.dialects.postgresql import JSONB

from src.models.database import Base, utc_now


class SystemLog(Base):
    """One log entry written by any service (pipeline, API, GUI, agents)."""

    __tablename__ = "system_logs"

    log_id    = Column(BigInteger, primary_key=True, autoincrement=True)
    timestamp = Column(DateTime(timezone=True), nullable=False, default=utc_now)
    level     = Column(String(20),  nullable=False, default="INFO")   # INFO/SUCCESS/WARNING/ERROR
    source    = Column(String(50),  nullable=False, default="system") # pipeline/simulation/agent/…
    component = Column(String(100), nullable=True)                    # e.g. ContentUnderstandingAgent
    message   = Column(Text,        nullable=False)
    details   = Column(JSONB,       nullable=True)

    __table_args__ = (
        Index("idx_syslog_ts",        "timestamp"),
        Index("idx_syslog_source_ts", "source",  "timestamp"),
        Index("idx_syslog_level_ts",  "level",   "timestamp"),
    )

    def __repr__(self) -> str:
        return f"<SystemLog({self.log_id}, {self.level}, {self.source}: {str(self.message)[:60]})>"
