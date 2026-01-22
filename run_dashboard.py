"""
Quick start script for TradeMeUp Dashboard
"""

import sys
import os

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from src.gui.app import app

if __name__ == "__main__":
    print("=" * 80)
    print("🚀 TradeMeUp Dashboard - AI Trading Intelligence")
    print("=" * 80)
    print("\n📊 Starting dashboard server...")
    print("🌐 Dashboard URL: http://localhost:8050")
    print("🌐 Network URL: http://0.0.0.0:8050")
    print("\n💡 Press CTRL+C to stop the server\n")
    print("=" * 80)
    
    app.run(debug=True, host="0.0.0.0", port=8050)
