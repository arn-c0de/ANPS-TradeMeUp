"""Quick check of simulation data with risk/position correlation."""
import sqlite3

conn = sqlite3.connect('trademeup.db')
cursor = conn.cursor()

print("=" * 100)
print("BEFORE FIX: Checking current simulations (OLD CODE)")
print("=" * 100)

cursor.execute('''
    SELECT entity_id, risk_score, position_size_pct, position_value_usd, expected_return_pct
    FROM trading_simulations 
    WHERE position_size_pct IS NOT NULL AND risk_score IS NOT NULL
    ORDER BY created_at DESC 
    LIMIT 20
''')
rows = cursor.fetchall()

if rows:
    print(f"\n{'Entity':<35} {'Risk':<7} {'Pos %':<8} {'Pos Value':<12} {'Expected'}")
    print("-" * 100)
    for row in rows:
        entity = (row[0][:32] + '..') if len(row[0]) > 34 else row[0]
        risk = row[1] or 0
        pos_pct = row[2] or 0
        pos_value = row[3] or 0
        expected = row[4] or 0
        print(f"{entity:<35} {risk:<7.3f} {pos_pct:<8.2f}% ${pos_value:<11,.0f} {expected:>+6.2f}%")
    
    # Calculate correlation
    risks = [r[1] for r in rows if r[1] and r[2]]
    pos_sizes = [r[2] for r in rows if r[1] and r[2]]
    
    if len(risks) > 3:
        avg_risk = sum(risks) / len(risks)
        avg_pos = sum(pos_sizes) / len(pos_sizes)
        
        high_risk_positions = [pos_sizes[i] for i in range(len(risks)) if risks[i] > avg_risk]
        low_risk_positions = [pos_sizes[i] for i in range(len(risks)) if risks[i] < avg_risk]
        
        if high_risk_positions and low_risk_positions:
            avg_high_risk_pos = sum(high_risk_positions) / len(high_risk_positions)
            avg_low_risk_pos = sum(low_risk_positions) / len(low_risk_positions)
            
            print(f"\n{'=' * 100}")
            print(f"CORRELATION CHECK (should be INVERSE):")
            print(f"  Average Risk: {avg_risk:.3f}")
            print(f"  Average Position %: {avg_pos:.2f}%")
            print(f"\n  High Risk (>{avg_risk:.3f}) trades: Avg Position = {avg_high_risk_pos:.2f}%")
            print(f"  Low Risk (<{avg_risk:.3f}) trades:  Avg Position = {avg_low_risk_pos:.2f}%")
            
            if avg_high_risk_pos < avg_low_risk_pos:
                diff = avg_low_risk_pos - avg_high_risk_pos
                print(f"\n  ✅ CORRECT: High risk → LOWER positions (by {diff:.2f}%)")
            else:
                diff = avg_high_risk_pos - avg_low_risk_pos
                print(f"\n  ❌ WRONG: High risk → HIGHER positions (by {diff:.2f}%)")
                print(f"     This is backwards! Should be inverse correlation.")
else:
    print("\nNo simulations found with both risk_score and position_size_pct")

print(f"{'=' * 100}\n")
conn.close()
