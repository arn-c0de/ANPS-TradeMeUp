"""Generate callbacks/charts/extended.py from app.py chart callbacks."""
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
APP = ROOT / "src" / "gui" / "app.py"
OUT = ROOT / "src" / "gui" / "callbacks" / "charts" / "extended.py"

with open(APP, encoding="utf-8") as f:
    content = f.read()

start = content.find("# ============================================================================\n# CALLBACKS - CHARTS TAB")
end = content.find('if __name__ == "__main__":')
if start == -1 or end == -1:
    raise SystemExit("Markers not found")

chunk = content[start:end].rstrip()
# Drop the section header (through first blank line after ============)
idx = chunk.find("\n\n", chunk.find("# ============================================================================"))
if idx != -1:
    chunk = chunk[idx + 2:]  # skip header and blank line

# Indent all lines by 4 spaces
lines = chunk.split("\n")
indented = []
for line in lines:
    if line.strip() == "":
        indented.append("")
    else:
        indented.append("    " + line)

body = "\n".join(indented)

# Replace engine with _engine (only Session usage)
body = body.replace("Session(engine)", "Session(_engine)")

header = '''"""
Chart tab extended callbacks: price cache, tabs, overlays, infinite scroll, render, panels.
"""

import concurrent.futures
import copy
import json
import logging
import time
import uuid
from pathlib import Path

import dash
import dash_bootstrap_components as dbc
from dash import ALL, MATCH, Input, Output, State, html
from dash.exceptions import PreventUpdate
from sqlalchemy.orm import Session

from src.models.database import engine as _engine
from src.gui.tabs import charts as charts_tab
from src.gui.charts.fullscreen_manager import get_fullscreen_state
from src.gui.charts.overlay_utils import normalize_overlay_store, save_overlays_to_db
from src.gui.charts.chart_utils import find_index_binary
from src.gui.charts.chart_data_manager import get_chart_data_manager

logger = logging.getLogger(__name__)


def register_charts_extended(app):
    """Register extended chart callbacks (tabs, overlays, render, panels)."""
'''
# Fix charts. -> charts_tab.
body = body.replace("charts.get_stock_chart_components", "charts_tab.get_stock_chart_components")
body = body.replace("charts.create_trading_overlay", "charts_tab.create_trading_overlay")
body = body.replace("charts.get_stock_chart", "charts_tab.get_stock_chart")
body = body.replace("charts.market_data", "charts_tab.market_data")

out_content = header + body + "\n"

OUT.write_text(out_content, encoding="utf-8")
print("Wrote", OUT)
