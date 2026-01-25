"""Diagnostic script to check simulation calculations and new risk components."""
import sqlite3
import json
from datetime import datetime, timedelta
from pathlib import Path

DB_PATH = "trademeup.db"

def check_recent_simulations():
    """Check recent simulations for completeness."""

    print("=" * 80)
    print("SIMULATION DATABASE DIAGNOSTIC REPORT")
    print("=" * 80)

    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()

    # Get total count
    cursor.execute("SELECT COUNT(*) as total FROM trading_simulations")
    total = cursor.fetchone()['total']
    print(f"\nTotal Simulations: {total}")

    if total == 0:
        print("\n[ERROR] No simulations found in database!")
        conn.close()
        return

    # Check recent simulations
    recent_cutoff = (datetime.now() - timedelta(days=1)).isoformat()
    cursor.execute("""
        SELECT * FROM trading_simulations
        WHERE created_at >= ?
        ORDER BY created_at DESC
        LIMIT 5
    """, (recent_cutoff,))
    recent_sims = cursor.fetchall()

    print(f"\nRecent Simulations (last 24h): {len(recent_sims)}")

    if not recent_sims:
        print("\n[WARNING] No recent simulations found! Checking older ones...")
        cursor.execute("""
            SELECT * FROM trading_simulations
            ORDER BY created_at DESC
            LIMIT 10
        """)
        recent_sims = cursor.fetchall()

    # Detailed inspection
    print("\n" + "=" * 80)
    print("DETAILED SPOT CHECK (First 5 Simulations)")
    print("=" * 80)

    for idx, sim in enumerate(recent_sims, 1):
        print(f"\n{'-' * 80}")
        print(f"Simulation #{idx}: {sim['entity_id']} ({sim['created_at']})")
        print(f"{'-' * 80}")

        print(f"  Prediction ID: {sim['prediction_id']}")
        print(f"  Decision: {sim['decision']}")
        print(f"  Horizon: {sim['horizon']}")
        print(f"  Risk Score: {sim['risk_score']:.4f}" if sim['risk_score'] else "  Risk Score: NULL")

        # Check OLD columns
        print(f"\n  [OLD] Cost Columns:")
        print(f"     transaction_cost_bps: {sim['transaction_cost_bps']:.2f}" if sim['transaction_cost_bps'] else "     transaction_cost_bps: NULL")

        # Check NEW columns
        print(f"\n  [NEW] Cost Columns:")
        print(f"     overnight_cost_bps: {sim['overnight_cost_bps']:.2f}" if sim['overnight_cost_bps'] else "     overnight_cost_bps: NULL")
        print(f"     borrow_cost_bps: {sim['borrow_cost_bps']:.2f}" if sim['borrow_cost_bps'] else "     borrow_cost_bps: NULL")

        print(f"\n  [NEW] Position Columns:")
        print(f"     position_size_pct: {sim['position_size_pct']:.2f}%" if sim['position_size_pct'] else "     position_size_pct: NULL")
        print(f"     position_value_usd: ${sim['position_value_usd']:,.2f}" if sim['position_value_usd'] else "     position_value_usd: NULL")

        # Check cost_breakdown JSON
        print(f"\n  Cost Breakdown JSON:")
        if sim['cost_breakdown']:
            cost_bd = json.loads(sim['cost_breakdown'])
            expected_keys = ['commission_bps', 'spread_bps', 'slippage_bps', 'market_impact_bps',
                           'overnight_cost_bps', 'borrow_cost_bps', 'regulatory_bps']

            present_keys = [k for k in expected_keys if k in cost_bd]
            missing_keys = [k for k in expected_keys if k not in cost_bd]

            print(f"     [+] Present ({len(present_keys)}/7): {', '.join(present_keys)}")
            if missing_keys:
                print(f"     [-] Missing ({len(missing_keys)}/7): {', '.join(missing_keys)}")

            # Show actual values
            for key in present_keys:
                print(f"       - {key}: {cost_bd[key]:.2f}")
        else:
            print(f"     [-] NULL - No cost breakdown available!")

        # Check risk_breakdown JSON
        print(f"\n  Risk Breakdown JSON:")
        if sim['risk_breakdown']:
            risk_bd = json.loads(sim['risk_breakdown'])
            expected_risk_keys = ['model_uncertainty', 'divergence_magnitude', 'volatility_regime',
                                'liquidity_stress', 'regime_instability', 'transaction_cost',
                                'market_impact', 'correlation_breakdown', 'position_concentration',
                                'liquidity_constraint']

            present_risk = [k for k in expected_risk_keys if k in risk_bd]
            missing_risk = [k for k in expected_risk_keys if k not in risk_bd]

            print(f"     [+] Present ({len(present_risk)}/10): {', '.join(present_risk)}")
            if missing_risk:
                print(f"     [-] Missing ({len(missing_risk)}/10): {', '.join(missing_risk)}")

            # Show NEW risk components specifically
            if 'position_concentration' in risk_bd:
                print(f"       - position_concentration: {risk_bd['position_concentration']:.4f} [NEW]")
            if 'liquidity_constraint' in risk_bd:
                print(f"       - liquidity_constraint: {risk_bd['liquidity_constraint']:.4f} [NEW]")
        else:
            print(f"     [-] NULL - No risk breakdown available!")

    # Statistics
    print("\n" + "=" * 80)
    print("AGGREGATE STATISTICS")
    print("=" * 80)

    # Count simulations with NULL new columns
    cursor.execute("SELECT COUNT(*) as count FROM trading_simulations WHERE overnight_cost_bps IS NULL")
    null_overnight = cursor.fetchone()['count']

    cursor.execute("SELECT COUNT(*) as count FROM trading_simulations WHERE borrow_cost_bps IS NULL")
    null_borrow = cursor.fetchone()['count']

    cursor.execute("SELECT COUNT(*) as count FROM trading_simulations WHERE position_size_pct IS NULL")
    null_position_size = cursor.fetchone()['count']

    cursor.execute("SELECT COUNT(*) as count FROM trading_simulations WHERE position_value_usd IS NULL")
    null_position_value = cursor.fetchone()['count']

    print(f"\n  NULL Value Counts:")
    print(f"    overnight_cost_bps: {null_overnight}/{total} ({null_overnight/total*100:.1f}%)")
    print(f"    borrow_cost_bps: {null_borrow}/{total} ({null_borrow/total*100:.1f}%)")
    print(f"    position_size_pct: {null_position_size}/{total} ({null_position_size/total*100:.1f}%)")
    print(f"    position_value_usd: {null_position_value}/{total} ({null_position_value/total*100:.1f}%)")

    # Check for complete simulations (all new columns populated)
    cursor.execute("""
        SELECT COUNT(*) as count FROM trading_simulations
        WHERE overnight_cost_bps IS NOT NULL
        AND borrow_cost_bps IS NOT NULL
        AND position_size_pct IS NOT NULL
        AND position_value_usd IS NOT NULL
    """)
    complete_sims = cursor.fetchone()['count']

    print(f"\n  Complete Simulations (all new columns): {complete_sims}/{total} ({complete_sims/total*100:.1f}%)")

    # Decision breakdown
    cursor.execute("""
        SELECT decision, COUNT(*) as count
        FROM trading_simulations
        GROUP BY decision
    """)
    decisions = cursor.fetchall()

    print(f"\n  Decision Distribution:")
    for row in decisions:
        print(f"    {row['decision']}: {row['count']} ({row['count']/total*100:.1f}%)")

    # Risk score statistics
    cursor.execute("""
        SELECT
            AVG(risk_score) as avg_risk,
            MAX(risk_score) as max_risk,
            MIN(risk_score) as min_risk
        FROM trading_simulations
        WHERE risk_score IS NOT NULL
    """)
    stats = cursor.fetchone()

    print(f"\n  Risk Score Statistics:")
    print(f"    Average: {stats['avg_risk']:.4f}" if stats['avg_risk'] else "    Average: NULL")
    print(f"    Min: {stats['min_risk']:.4f}" if stats['min_risk'] else "    Min: NULL")
    print(f"    Max: {stats['max_risk']:.4f}" if stats['max_risk'] else "    Max: NULL")

    # DIAGNOSIS
    print("\n" + "=" * 80)
    print("DIAGNOSIS")
    print("=" * 80)

    issues = []

    if null_overnight == total:
        issues.append("[WARN] ALL simulations have NULL overnight_cost_bps - simulations created BEFORE enhancement")
    elif null_overnight > total * 0.5:
        issues.append(f"[WARN] {null_overnight/total*100:.0f}% of simulations missing overnight costs")

    if null_position_size == total:
        issues.append("[WARN] ALL simulations have NULL position_size_pct - simulations created BEFORE enhancement")

    if complete_sims == 0:
        issues.append("[ERROR] NO simulations have complete new cost/position data")
        issues.append("[RECOMMENDATION] Re-run simulation engine to populate new columns")
    elif complete_sims < total * 0.1:
        issues.append(f"[WARN] Only {complete_sims/total*100:.1f}% of simulations have complete data")
        issues.append("[RECOMMENDATION] Consider re-running simulations for recent predictions")

    # Check a sample for cost breakdown completeness
    cursor.execute("SELECT cost_breakdown FROM trading_simulations WHERE cost_breakdown IS NOT NULL LIMIT 1")
    sample = cursor.fetchone()

    if sample and sample['cost_breakdown']:
        cost_bd = json.loads(sample['cost_breakdown'])
        if 'overnight_cost_bps' not in cost_bd or 'borrow_cost_bps' not in cost_bd:
            issues.append("[WARN] cost_breakdown JSON missing new components (overnight_cost_bps, borrow_cost_bps)")

    if issues:
        print("\n  Issues Found:")
        for issue in issues:
            print(f"    {issue}")
    else:
        print("\n  [OK] No critical issues found! All simulations have complete enhanced data.")

    print("\n" + "=" * 80)

    conn.close()

if __name__ == "__main__":
    check_recent_simulations()
