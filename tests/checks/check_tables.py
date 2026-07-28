"""Check database tables."""
import sys
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))

from sqlalchemy import text

from src.models.database import engine

print("Checking PostgreSQL database tables...")

with engine.connect() as conn:
    # Query PostgreSQL information schema for table list
    result = conn.execute(text("""
        SELECT table_name 
        FROM information_schema.tables 
        WHERE table_schema = 'public' 
        AND table_type = 'BASE TABLE'
        ORDER BY table_name
    """))

    tables = [row[0] for row in result.fetchall()]

    print(f"\nFound {len(tables)} tables:")
    for table in tables:
        # Get row count for each table
        count_result = conn.execute(text(f"SELECT COUNT(*) FROM {table}"))
        count = count_result.scalar()
        print(f"  - {table:30} ({count:,} rows)")

print("\n[SUCCESS] Database check complete")
