"""Simple test to verify imports and basic setup."""
import sys
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

print("Testing imports...")

try:
    from src.models.database import SessionLocal, engine
    print("✓ Database imports OK")
except Exception as e:
    print(f"✗ Database import failed: {e}")
    sys.exit(1)

try:
    from src.config.settings import settings
    from src.utils.redact import redact_url
    print(f"✓ Settings OK - LLM Provider: {settings.llm_provider}")
    print(f"  Database: {redact_url(settings.database_url)}")
    print(f"  Ollama: {redact_url(settings.ollama_base_url)}")
    print(f"  Model: {settings.ollama_model}")
except Exception as e:
    print(f"✗ Settings failed: {e}")
    sys.exit(1)

try:
    from src.agents.ingestion_agent import IngestionAgent
    print("✓ IngestionAgent import OK")
except Exception as e:
    print(f"✗ IngestionAgent failed: {e}")
    sys.exit(1)

try:
    # Test database connection
    db = SessionLocal()
    print("✓ Database connection OK")
    
    # Test basic query
    from src.models.raw_news import RawNews
    count = db.query(RawNews).count()
    print(f"✓ Database query OK - {count} articles in DB")
    
    db.close()
except Exception as e:
    print(f"✗ Database test failed: {e}")
    sys.exit(1)

print("\n✅ All basic tests passed!")
print("\nNow testing agent initialization...")

try:
    db = SessionLocal()
    agent = IngestionAgent(db)
    print("✓ IngestionAgent initialized")
    
    stats = agent.get_statistics()
    print(f"✓ Stats: {stats}")
    
    db.close()
except Exception as e:
    print(f"✗ Agent test failed: {e}")
    import traceback
    traceback.print_exc()
    sys.exit(1)

print("\n✅ All tests passed! System is ready.")
