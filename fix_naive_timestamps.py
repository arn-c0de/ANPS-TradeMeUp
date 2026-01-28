"""
Migration script to convert naive timestamps to timezone-aware timestamps.
This fixes the timezone issue after migrating from SQLite to PostgreSQL.
"""
from datetime import timezone
from sqlalchemy import text
from src.models.database import engine

def fix_naive_timestamps():
    """
    Convert all naive UTC timestamps to timezone-aware timestamps.
    
    PostgreSQL with timezone=True expects timezone-aware datetimes.
    This script updates all existing naive timestamps by adding UTC timezone.
    """
    print("=" * 80)
    print("Converting Naive Timestamps to Timezone-Aware (UTC)")
    print("=" * 80)
    
    tables_and_columns = [
        ("raw_news", ["published_at", "fetched_at", "created_at"]),
        ("processed_news", ["processing_timestamp"]),
        ("predictions", ["timestamp", "created_at"]),
        ("prediction_outcomes", ["evaluation_timestamp", "created_at"]),
        ("prediction_performance", ["created_at"]),
        ("entities", ["created_at", "updated_at"]),
        ("trading_simulations", ["created_at"]),
        ("data_quality_scores", ["created_at"]),
        ("market_regimes", ["regime_start", "regime_end", "created_at"]),
        ("surprise_scores", ["created_at"]),
        ("fact_verifications", ["verified_at"]),
        ("chart_overlays", ["created_at"]),
    ]
    
    with engine.connect() as conn:
        for table_name, columns in tables_and_columns:
            print(f"\n📋 Processing table: {table_name}")
            
            for column in columns:
                try:
                    # Check if table exists
                    result = conn.execute(text(f"""
                        SELECT EXISTS (
                            SELECT FROM information_schema.tables 
                            WHERE table_name = '{table_name}'
                        );
                    """))
                    table_exists = result.scalar()
                    
                    if not table_exists:
                        print(f"   ⚠️  Table '{table_name}' does not exist, skipping...")
                        break
                    
                    # Check if column exists
                    result = conn.execute(text(f"""
                        SELECT EXISTS (
                            SELECT FROM information_schema.columns 
                            WHERE table_name = '{table_name}' AND column_name = '{column}'
                        );
                    """))
                    column_exists = result.scalar()
                    
                    if not column_exists:
                        print(f"   ⚠️  Column '{column}' does not exist, skipping...")
                        continue
                    
                    # For PostgreSQL, timestamps without timezone info are stored as naive
                    # We need to convert them to timezone-aware by adding 'UTC' timezone
                    
                    # First, check how many rows need updating
                    result = conn.execute(text(f"""
                        SELECT COUNT(*) 
                        FROM {table_name} 
                        WHERE {column} IS NOT NULL 
                        AND {column}::text NOT LIKE '%+%' 
                        AND {column}::text NOT LIKE '%-__:__';
                    """))
                    count = result.scalar() or 0
                    
                    if count == 0:
                        print(f"   ✓ {column}: No naive timestamps found")
                        continue
                    
                    print(f"   🔄 {column}: Converting {count} naive timestamps...")
                    
                    # Update the timestamps by treating them as UTC
                    # AT TIME ZONE 'UTC' interprets the timestamp as UTC and makes it timezone-aware
                    conn.execute(text(f"""
                        UPDATE {table_name} 
                        SET {column} = {column} AT TIME ZONE 'UTC'
                        WHERE {column} IS NOT NULL 
                        AND {column}::text NOT LIKE '%+%' 
                        AND {column}::text NOT LIKE '%-__:__';
                    """))
                    
                    print(f"   ✓ {column}: Converted {count} timestamps to timezone-aware")
                    
                except Exception as e:
                    print(f"   ❌ Error processing {table_name}.{column}: {str(e)}")
                    continue
            
        conn.commit()
    
    print("\n" + "=" * 80)
    print("✓ Timestamp conversion complete!")
    print("=" * 80)
    print("\nRun 'python test_timezone_fix.py' to verify the fix.")

if __name__ == "__main__":
    fix_naive_timestamps()
