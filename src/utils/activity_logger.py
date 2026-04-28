"""Activity Logger — real-time agent activity tracking and central DB log store."""

import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional


# Level → normalised form used in system_logs
_LEVEL_MAP = {
    "STARTING":   "INFO",
    "PROCESSING": "INFO",
    "COMPLETED":  "SUCCESS",
    "SUCCESS":    "SUCCESS",
    "INFO":       "INFO",
    "WARNING":    "WARNING",
    "ERROR":      "ERROR",
    "DEBUG":      "DEBUG",
}

_MAX_LOG_ROWS   = 20_000   # prune target
_PRUNE_INTERVAL = 200      # prune check every N writes


class ActivityLogger:
    """Logger for agent activities — writes to log files AND PostgreSQL system_logs."""

    def __init__(self, log_dir: str = "logs"):
        self.log_dir = Path(log_dir)
        self.log_dir.mkdir(exist_ok=True)
        self.activity_log  = self.log_dir / "pipeline_activity.log"
        self.dashboard_log = self.log_dir / "dashboard.log"
        self._write_count  = 0

    # ── public API ────────────────────────────────────────────────────────────

    def log_activity(
        self,
        message:   str,
        level:     str = "INFO",
        source:    str = "pipeline",
        component: Optional[str] = None,
        details:   Optional[Any] = None,
    ):
        """Log a message to the flat files and to the system_logs DB table."""
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        log_entry = f"[{timestamp}] {level}: {message}\n"

        # ── file writes (always, non-blocking) ───────────────────────────────
        try:
            with open(self.activity_log, "a", encoding="utf-8") as f:
                f.write(log_entry)
            with open(self.dashboard_log, "a", encoding="utf-8") as f:
                f.write(log_entry)
        except OSError:
            pass

        print(log_entry.strip())

        # ── DB write (best-effort, never raises) ─────────────────────────────
        self._write_to_db(level, source, component, message, details)

        # ── periodic prune ───────────────────────────────────────────────────
        self._write_count += 1
        if self._write_count % _PRUNE_INTERVAL == 0:
            self._prune_old_logs()

    # ── convenience wrappers (backward-compatible) ────────────────────────────

    def log_agent_start(self, agent_name: str, phase: Optional[str] = None):
        phase_text = f" — Phase {phase}" if phase else ""
        self.log_activity(
            f"STARTING {agent_name}{phase_text}", "STARTING",
            source="agent", component=agent_name,
        )

    def log_agent_processing(self, agent_name: str, item: str, current: int, total: int):
        self.log_activity(
            f"PROCESSING {agent_name}: {item} ({current}/{total})", "PROCESSING",
            source="agent", component=agent_name,
        )

    def log_agent_success(self, agent_name: str, count: int, duration: Optional[float] = None):
        duration_text = f" in {duration:.2f}s" if duration else ""
        self.log_activity(
            f"SUCCESS {agent_name}: Processed {count} items{duration_text}", "SUCCESS",
            source="agent", component=agent_name,
            details={"count": count, "duration_s": duration},
        )

    def log_agent_error(self, agent_name: str, error: str):
        self.log_activity(
            f"ERROR {agent_name}: {error}", "ERROR",
            source="agent", component=agent_name,
            details={"error": error[:500]},
        )

    def log_pipeline_start(self, pipeline_name: str = "MVP Pipeline"):
        self.log_activity("=" * 60, "INFO", source="pipeline")
        self.log_activity(f">> {pipeline_name} STARTED", "STARTING",
                          source="pipeline", component=pipeline_name)
        self.log_activity("=" * 60, "INFO", source="pipeline")

    def log_pipeline_complete(self, pipeline_name: str = "MVP Pipeline",
                              duration: Optional[float] = None):
        duration_text = f" in {duration:.2f}s" if duration else ""
        self.log_activity(
            f">> {pipeline_name} COMPLETED{duration_text}", "SUCCESS",
            source="pipeline", component=pipeline_name,
            details={"duration_s": duration},
        )
        self.log_activity("=" * 60, "INFO", source="pipeline")

    def log_phase(self, phase_num, phase_name: str):
        self.log_activity("", "INFO", source="pipeline")
        self.log_activity(f">> PHASE {phase_num}: {phase_name}", "INFO",
                          source="pipeline", component=f"Phase {phase_num}")
        self.log_activity("-" * 60, "INFO", source="pipeline")

    def clear_logs(self):
        if self.activity_log.exists():
            self.activity_log.unlink()
        if self.dashboard_log.exists():
            self.dashboard_log.unlink()

    # ── internals ─────────────────────────────────────────────────────────────

    def _write_to_db(
        self,
        level:     str,
        source:    str,
        component: Optional[str],
        message:   str,
        details:   Optional[Any],
    ):
        """Insert one row into system_logs. Never raises."""
        try:
            from src.models.database import SessionLocal
            from src.models.system_logs import SystemLog

            norm_level = _LEVEL_MAP.get(level.upper(), "INFO")
            entry = SystemLog(
                timestamp = datetime.now(timezone.utc),
                level     = norm_level,
                source    = source[:50],
                component = (component or "")[:100] or None,
                message   = message[:4000],
                details   = details if isinstance(details, (dict, list)) else None,
            )
            with SessionLocal() as db:
                db.add(entry)
                db.commit()
        except Exception:
            pass  # log failures must never break the application

    def _prune_old_logs(self):
        """Keep the table below _MAX_LOG_ROWS by deleting the oldest excess rows."""
        try:
            from src.models.database import SessionLocal
            from src.models.system_logs import SystemLog
            from sqlalchemy import func, text

            with SessionLocal() as db:
                total = db.query(func.count(SystemLog.log_id)).scalar() or 0
                excess = total - _MAX_LOG_ROWS
                if excess > 0:
                    db.execute(text(
                        "DELETE FROM system_logs WHERE log_id IN "
                        "(SELECT log_id FROM system_logs ORDER BY log_id ASC LIMIT :n)"
                    ), {"n": excess})
                    db.commit()
        except Exception:
            pass


# Global singleton
activity_logger = ActivityLogger()
