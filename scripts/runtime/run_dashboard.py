"""Runtime entrypoint for the TradeMeUp dashboard."""

import os
import sys
import warnings
from pathlib import Path

# Suppress pandas deprecation warnings from yfinance library
warnings.filterwarnings("ignore", category=DeprecationWarning, module="yfinance")
warnings.filterwarnings("ignore", message=".*Timestamp.utcnow.*")

PROJECT_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(PROJECT_ROOT))

from src.gui.app import app
from src.utils.activity_logger import activity_logger

if __name__ == "__main__":
    debug_mode = os.getenv("DASH_DEBUG", "").lower() in {"1", "true", "yes"}
    # Loopback by default: the dashboard has no authentication and can launch
    # pipeline processes. docker-compose sets DASH_HOST=0.0.0.0 so the container
    # stays reachable from the host, where Docker controls the port mapping.
    host = os.getenv("DASH_HOST", "127.0.0.1")

    # Initialize activity logger with startup message
    activity_logger.log_activity("Dashboard starting...", "INFO")
    activity_logger.log_activity("System ready for pipeline execution", "SUCCESS")
    activity_logger.log_activity("Waiting for user action...", "INFO")

    print("=" * 80)
    print(">> TradeMeUp Dashboard - AI Trading Intelligence")
    print("=" * 80)
    print("\n[DASHBOARD] Starting dashboard server...")
    print("[URL] Dashboard URL: http://localhost:8050")
    print(f"[URL] Listening on: {host}:8050")
    print("\n[INFO] Press CTRL+C to stop the server\n")
    print("=" * 80)

    # Enable hot reload and asset refresh in debug mode
    app.run(
        debug=debug_mode,
        host=host,
        port=8050,
        dev_tools_hot_reload=debug_mode,
        dev_tools_ui=debug_mode,
        dev_tools_props_check=False  # Disable to reduce console warnings
    )
