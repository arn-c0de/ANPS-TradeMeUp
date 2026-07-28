"""Shared retention helpers for the system_logs table."""

from datetime import UTC, datetime, timedelta, timezone

MAX_SYSTEM_LOG_ROWS = 20_000
LOG_RETENTION_HOURS = 24


def prune_system_logs() -> None:
    """Delete expired logs and keep the table below the max row target."""
    try:
        from sqlalchemy import func, text

        from src.models.database import SessionLocal
        from src.models.system_logs import SystemLog

        cutoff = datetime.now(UTC) - timedelta(hours=LOG_RETENTION_HOURS)

        with SessionLocal() as db:
            db.query(SystemLog).filter(SystemLog.timestamp < cutoff).delete(
                synchronize_session=False
            )

            total = db.query(func.count(SystemLog.log_id)).scalar() or 0
            excess = total - MAX_SYSTEM_LOG_ROWS
            if excess > 0:
                db.execute(
                    text(
                        "DELETE FROM system_logs WHERE log_id IN "
                        "(SELECT log_id FROM system_logs ORDER BY log_id ASC LIMIT :n)"
                    ),
                    {"n": excess},
                )

            db.commit()
    except Exception:
        pass
