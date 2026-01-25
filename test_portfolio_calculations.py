"""Test script to verify portfolio position calculations."""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent / "src"))

# Import database first to avoid table redefinition
from models.database import get_scoped_session
from models.trading_simulation import TradingSimulation
from simulations.trading_simulator import TradingSimulationEngine
from sqlalchemy import desc

def test_portfolio_calculations():
    print("=" * 80)
    print("PORTFOLIO CALCULATION TEST")
    print("=" * 80)

    # Run simulation engine for a few predictions
    print("\n1. Creating new simulations with enhanced calculations...")
    engine = TradingSimulationEngine()

    # Process a small batch
    stats = engine.process_batch(limit=5, lookback_days=1)

    print(f"\nSimulation Stats:")
    print(f"  Processed: {stats['processed']}")
    print(f"  Created: {stats['created']}")
    print(f"  Updated: {stats['updated']}")
    print(f"  Errors: {stats['errors']}")

    # Check the results
    print("\n2. Checking newly created simulations...")
    with get_scoped_session() as db:
        recent_sims = db.query(TradingSimulation)\
            .order_by(desc(TradingSimulation.created_at))\
            .limit(5)\
            .all()

        print(f"\nFound {len(recent_sims)} recent simulations:")
        print(f"\n{'Entity':<30} {'Cost (bps)':<12} {'Pos %':<10} {'Pos Value':<15} {'O/N bps':<10} {'Borrow bps':<12}")
        print("-" * 100)

        for sim in recent_sims:
            entity_name = sim.entity_id[:30] if len(sim.entity_id) > 30 else sim.entity_id
            cost_bps = sim.transaction_cost_bps or 0
            pos_pct = sim.position_size_pct or 0
            pos_value = sim.position_value_usd or 0
            overnight = sim.overnight_cost_bps or 0
            borrow = sim.borrow_cost_bps or 0

            print(f"{entity_name:<30} {cost_bps:<12.2f} {pos_pct:<10.2f} ${pos_value:<14,.0f} {overnight:<10.2f} {borrow:<12.2f}")

        # Check if values are populated
        has_position_size = sum(1 for s in recent_sims if s.position_size_pct and s.position_size_pct > 0)
        has_costs = sum(1 for s in recent_sims if s.transaction_cost_bps and s.transaction_cost_bps > 0)

        print(f"\n{'=' * 100}")
        print(f"VALIDATION:")
        print(f"  Simulations with position_size_pct > 0: {has_position_size}/{len(recent_sims)}")
        print(f"  Simulations with transaction_cost_bps > 0: {has_costs}/{len(recent_sims)}")

        if has_position_size == 0:
            print(f"\n❌ ERROR: No simulations have position_size_pct calculated!")
            print(f"   This indicates the simulation engine is not using the enhanced code.")
        elif has_costs == 0:
            print(f"\n❌ ERROR: No simulations have transaction costs calculated!")
        else:
            print(f"\n✅ SUCCESS: Portfolio calculations are working correctly!")

        # Show one detailed example
        if recent_sims:
            print(f"\n{'=' * 100}")
            print(f"DETAILED EXAMPLE (First Simulation):")
            sim = recent_sims[0]
            print(f"  Entity: {sim.entity_id}")
            print(f"  Decision: {sim.decision}")
            print(f"  Horizon: {sim.horizon}")
            print(f"  Risk Score: {sim.risk_score:.4f}")
            print(f"\n  Cost Breakdown:")
            if sim.cost_breakdown:
                for key, value in sim.cost_breakdown.items():
                    print(f"    {key}: {value:.2f}")
            print(f"\n  Position Info:")
            print(f"    position_size_pct: {sim.position_size_pct:.2f}%" if sim.position_size_pct else "    position_size_pct: NULL")
            print(f"    position_value_usd: ${sim.position_value_usd:,.0f}" if sim.position_value_usd else "    position_value_usd: NULL")

    print(f"\n{'=' * 100}")

if __name__ == "__main__":
    test_portfolio_calculations()
