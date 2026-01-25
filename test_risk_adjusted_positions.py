"""Test risk-adjusted position sizing."""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent / "src"))

from models.database import get_scoped_session
from models.trading_simulation import TradingSimulation
from sqlalchemy import desc

print("=" * 100)
print("RISK-ADJUSTED POSITION SIZING TEST")
print("=" * 100)

# Check existing simulations
with get_scoped_session() as db:
    recent_sims = db.query(TradingSimulation)\
        .order_by(desc(TradingSimulation.created_at))\
        .limit(20)\
        .all()

    print(f"\nRecent Simulations (sorted by creation time):")
    print(f"\n{'Entity':<35} {'Risk':<7} {'Pos %':<8} {'Base $':<10} {'Expected':<10}")
    print("-" * 100)

    for s in recent_sims:
        entity = (s.entity_id[:32] + '..') if len(s.entity_id) > 34 else s.entity_id
        risk = s.risk_score or 0
        pos_pct = s.position_size_pct or 0
        # Calculate what base would have been (100 shares * price)
        # We don't have price directly, but can estimate from position_value_usd
        pos_value = s.position_value_usd or 0
        expected_return = s.expected_return_pct or 0
        
        print(f"{entity:<35} {risk:<7.3f} {pos_pct:<8.2f}% ${pos_value:<9,.0f} {expected_return:>+6.2f}%")

    print(f"\n{'=' * 100}")
    print("CORRELATION CHECK: Should see INVERSE relationship (higher risk = lower position %)")
    
    # Calculate correlation
    risks = [s.risk_score for s in recent_sims if s.risk_score and s.position_size_pct]
    pos_sizes = [s.position_size_pct for s in recent_sims if s.risk_score and s.position_size_pct]
    
    if len(risks) > 3:
        import statistics
        avg_risk = statistics.mean(risks)
        avg_pos = statistics.mean(pos_sizes)
        
        # Check if higher-than-average risk leads to lower-than-average position
        high_risk_positions = [pos_sizes[i] for i in range(len(risks)) if risks[i] > avg_risk]
        low_risk_positions = [pos_sizes[i] for i in range(len(risks)) if risks[i] < avg_risk]
        
        if high_risk_positions and low_risk_positions:
            avg_high_risk_pos = statistics.mean(high_risk_positions)
            avg_low_risk_pos = statistics.mean(low_risk_positions)
            
            print(f"\nAverage Position % for:")
            print(f"  High Risk (>{avg_risk:.3f}): {avg_high_risk_pos:.2f}%")
            print(f"  Low Risk (<{avg_risk:.3f}): {avg_low_risk_pos:.2f}%")
            
            if avg_high_risk_pos < avg_low_risk_pos:
                print(f"\n✅ CORRECT: High risk trades have LOWER position sizes!")
                print(f"   Difference: {avg_low_risk_pos - avg_high_risk_pos:.2f}% smaller for high-risk")
            else:
                print(f"\n❌ WRONG: High risk trades have HIGHER position sizes!")
                print(f"   This is backwards - need to fix the logic!")
    
    print(f"{'=' * 100}\n")
