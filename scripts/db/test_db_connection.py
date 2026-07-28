#!/usr/bin/env python3
"""Quick database connection test."""

import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(PROJECT_ROOT))

from sqlalchemy import create_engine, text

from src.config.settings import settings
from src.models.database import normalize_database_url


def main() -> int:
    """Test the configured PostgreSQL connection."""
    try:
        print("Testing PostgreSQL connection...")
        engine = create_engine(normalize_database_url(settings.database_url))

        with engine.connect() as conn:
            result = conn.execute(text("SELECT version()"))
            version = result.fetchone()[0]
            print("Connected successfully.")
            print(f"  PostgreSQL: {version.split(',')[0]}")

            result = conn.execute(
                text(
                    "SELECT COUNT(*) "
                    "FROM information_schema.tables "
                    "WHERE table_schema = 'public'"
                )
            )
            table_count = result.fetchone()[0]
            print(f"  Tables: {table_count}")

        return 0
    except Exception as exc:
        print(f"Connection failed: {exc}")
        return 1


if __name__ == "__main__":
    sys.exit(main())
