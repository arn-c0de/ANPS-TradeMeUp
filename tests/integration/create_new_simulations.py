"""Create new simulations with enhanced portfolio calculations."""
import sys
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent / "src"))

import logging

logging.basicConfig(level=logging.INFO)

print("=" * 80)
print("CREATING NEW SIMULATIONS WITH PORTFOLIO CALCULATIONS")
print("=" * 80)

# Import after path is set
from simulations.trading_simulator import TradingSimulationEngine

print("\nInitializing Trading Simulation Engine...")
engine = TradingSimulationEngine()

print("\nProcessing predictions and creating simulations...")
print("(This will calculate position sizes, costs, and risk scores)\n")

# Create simulations for recent predictions
stats = engine.process_batch(limit=50, lookback_days=7)

print("\n" + "=" * 80)
print("SIMULATION CREATION COMPLETE")
print("=" * 80)
print("\nStatistics:")
print(f"  Total Processed: {stats['processed']}")
print(f"  Created: {stats['created']}")
print(f"  Updated: {stats['updated']}")
print(f"  Errors: {stats['errors']}")

if stats['created'] > 0 or stats['updated'] > 0:
    print(f"\n✅ SUCCESS: Created/updated {stats['created'] + stats['updated']} simulations")
    print("   These simulations now include:")
    print("   - Position size %")
    print("   - Position value in USD")
    print("   - Overnight financing costs")
    print("   - Borrow costs")
    print("   - Complete risk breakdown (10 components)")
    print("   - Detailed cost breakdown (7 components)")
else:
    print("\n⚠️  No simulations were created. This may mean:")
    print("   - No predictions found in the specified date range")
    print("   - All predictions already have up-to-date simulations")

print("\n" + "=" * 80)
print("You can now refresh the GUI to see the new simulations with portfolio recommendations!")
print("=" * 80)
