"""Check database tables."""
import sqlite3

conn = sqlite3.connect('trademeup.db')
cursor = conn.cursor()
cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
tables = [row[0] for row in cursor.fetchall()]
print(f"Found {len(tables)} tables:")
for table in sorted(tables):
    print(f"  - {table}")
conn.close()
