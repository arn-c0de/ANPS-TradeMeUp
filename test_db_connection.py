#!/usr/bin/env python3
"""Quick database connection test"""
import sys
try:
    from sqlalchemy import create_engine, text
    
    DATABASE_URL = "postgresql://trademeup_user:trademeup_pass@localhost:5432/trademeup"
    
    print("Testing PostgreSQL connection...")
    engine = create_engine(DATABASE_URL)
    
    with engine.connect() as conn:
        result = conn.execute(text("SELECT version()"))
        version = result.fetchone()[0]
        print(f"✅ Connected successfully!")
        print(f"   PostgreSQL: {version.split(',')[0]}")
        
        # Count tables
        result = conn.execute(text(
            "SELECT COUNT(*) FROM information_schema.tables WHERE table_schema = 'public'"
        ))
        table_count = result.fetchone()[0]
        print(f"   Tables: {table_count}")
        
    sys.exit(0)
    
except Exception as e:
    print(f"❌ Connection failed: {e}")
    sys.exit(1)
