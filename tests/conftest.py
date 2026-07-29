"""Shared pytest configuration.

A handful of tests exercise the real database rather than a fake. Without a
running PostgreSQL they used to fail with a SQLAlchemy connection error, which
reads as "the code is broken" when it only means "no database here" - and it
left a clean checkout with a red suite. They are marked instead, and skipped
when the database genuinely cannot be reached.
"""
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent))

DATABASE_MARKER = "requires_database"

# Probed once per session: a connection attempt per test would be slow, and
# the answer cannot change mid-run in any way we care about.
_database_available: bool | None = None


def _probe_database() -> bool:
    """Whether the configured database accepts a connection."""
    try:
        from sqlalchemy import text

        from src.models.database import engine

        with engine.connect() as connection:
            connection.execute(text("SELECT 1"))
        return True
    except Exception:
        return False


def database_available() -> bool:
    global _database_available

    if _database_available is None:
        _database_available = _probe_database()

    return _database_available


def pytest_configure(config):
    config.addinivalue_line(
        "markers",
        f"{DATABASE_MARKER}: test needs a reachable PostgreSQL instance",
    )


def pytest_collection_modifyitems(config, items):
    if database_available():
        return

    skip = pytest.mark.skip(
        reason="no reachable database (start it with `docker compose up -d postgres`)"
    )
    for item in items:
        if DATABASE_MARKER in item.keywords:
            item.add_marker(skip)
