"""Create chart_overlays table in database."""
import sys
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from src.models.database import Base, engine
from src.models.chart_overlays import ChartOverlay

def create_table():
    """Create the chart_overlays table."""
    print("Creating chart_overlays table...")

    # Create only the ChartOverlay table
    ChartOverlay.__table__.create(engine, checkfirst=True)

    print("[OK] Table 'chart_overlays' created successfully!")

if __name__ == "__main__":
    create_table()
