import sqlite3
conn = sqlite3.connect('trademeup.db')
cursor = conn.cursor()
cursor.execute('SELECT entity_id, transaction_cost_bps, position_size_pct, position_value_usd, overnight_cost_bps, borrow_cost_bps FROM trading_simulations ORDER BY created_at DESC LIMIT 10')
rows = cursor.fetchall()
print(f"{'Entity':<35} {'Cost (bps)':<12} {'Pos %':<10} {'Pos Value':<15} {'O/N bps':<10} {'Borrow bps'}")
print("-" * 100)
for row in rows:
    entity = (row[0][:32] + '..') if len(row[0]) > 34 else row[0]
    cost = row[1] or 0
    pos_pct = row[2] or 0
    pos_val = row[3] or 0
    overnight = row[4] or 0
    borrow = row[5] or 0
    print(f"{entity:<35} {cost:<12.2f} {pos_pct:<10.2f} ${pos_val:<14,.0f} {overnight:<10.2f} {borrow:<10.2f}")
conn.close()
