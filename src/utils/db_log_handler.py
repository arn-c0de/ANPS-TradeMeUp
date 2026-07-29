"""Python logging.Handler that writes records to the system_logs DB table."""
import logging
from datetime import UTC, datetime

from src.utils.log_retention import prune_system_logs

_PY_TO_APP_LEVEL = {
    logging.DEBUG:    "DEBUG",
    logging.INFO:     "INFO",
    logging.WARNING:  "WARNING",
    logging.ERROR:    "ERROR",
    logging.CRITICAL: "ERROR",
}

# Third-party logger prefixes that are too noisy — only WARNING+ from these
_NOISY_PREFIXES = (
    "sqlalchemy", "uvicorn", "fastapi", "httpx", "httpcore",
    "urllib3", "asyncio", "yfinance", "hpack", "h2",
)
_PRUNE_INTERVAL = 200


def _is_noisy(name: str) -> bool:
    return any(name.startswith(p) for p in _NOISY_PREFIXES)


class DBLogHandler(logging.Handler):
    """Inserts Python log records into the system_logs PostgreSQL table.

    Attach to the root logger (or a specific logger) after the DB is ready:

        from src.utils.db_log_handler import DBLogHandler
        logging.getLogger().addHandler(DBLogHandler(source="api"))
    """

    def __init__(self, source: str = "system", level: int = logging.INFO):
        super().__init__(level)
        self.source = source[:50]
        self._write_count = 0

    def emit(self, record: logging.LogRecord):
        try:
            # Skip noisy third-party logs below WARNING
            if _is_noisy(record.name) and record.levelno < logging.WARNING:
                return

            from src.models.database import SessionLocal
            from src.models.system_logs import SystemLog

            app_level = _PY_TO_APP_LEVEL.get(record.levelno, "INFO")
            message   = self.format(record)[:4000]
            details   = None

            if record.exc_info:
                import traceback
                details = {
                    "exception": "".join(traceback.format_exception(*record.exc_info))[:2000]
                }

            entry = SystemLog(
                timestamp = datetime.fromtimestamp(record.created, tz=UTC),
                level     = app_level,
                source    = self.source,
                component = record.name[:100],
                message   = message,
                details   = details,
            )
            with SessionLocal() as db:
                db.add(entry)
                db.commit()

            self._write_count += 1
            if self._write_count % _PRUNE_INTERVAL == 0:
                prune_system_logs()
        except Exception:
            pass  # never let log handler errors propagate


def attach_db_handler(source: str = "system", level: int = logging.INFO) -> DBLogHandler:
    """Convenience: create a DBLogHandler and attach it to the root logger."""
    handler = DBLogHandler(source=source, level=level)
    handler.setFormatter(logging.Formatter("%(message)s"))
    logging.getLogger().addHandler(handler)
    return handler
