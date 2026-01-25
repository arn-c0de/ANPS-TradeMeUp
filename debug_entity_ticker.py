"""Debug script to check entity ticker mappings and identify issues"""
import logging
from sqlalchemy import and_, or_
from sqlalchemy.orm import Session
from src.models.database import engine
from src.models.entities import Entity
from src.models.predictions import Prediction
from src.models.trading_simulation import TradingSimulation
from src.models.raw_news import RawNews
from src.models.entities import NewsEntityMapping
from src.services.market_data import MarketDataProvider

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def check_entity_ticker_issues():
    """Check for entities with problematic ticker symbols"""
    with Session(engine) as db:
        # Get all entities that have predictions or simulations
        entities = db.query(Entity).all()
        
        print("\n" + "="*80)
        print("CHECKING ENTITY TICKER MAPPINGS")
        print("="*80)
        
        market_data = MarketDataProvider()
        
        # Check each entity
        problematic_entities = []
        
        for entity in entities:
            # Check if entity has predictions
            pred_count = db.query(Prediction).filter(
                Prediction.entity_id == entity.entity_id
            ).count()
            
            # Check if entity has simulations
            sim_count = db.query(TradingSimulation).filter(
                TradingSimulation.entity_id == entity.entity_id
            ).count()
            
            if pred_count == 0 and sim_count == 0:
                continue  # Skip entities without predictions/simulations
            
            # Try to fetch market data
            market_snapshot = market_data.get_live_price(entity.entity_id)
            has_market_data = market_snapshot is not None and market_snapshot.get('price', 0) > 0
            
            print(f"\n{'OK' if has_market_data else 'FAIL'} Entity: {entity.entity_name} (ID: {entity.entity_id})")
            print(f"   Type: {entity.entity_type}")
            print(f"   Predictions: {pred_count}, Simulations: {sim_count}")
            
            if not has_market_data:
                print(f"   WARNING: NO MARKET DATA FOUND")
                
                # Check if entity_id looks like a ticker or a company name
                if entity.entity_id.startswith('COMP_') or len(entity.entity_id) > 5:
                    print(f"   FOUND: This looks like a fallback or invalid ticker")
                
                # Check metadata for suggested ticker
                metadata = entity.metadata_ or {}
                suggested_ticker = metadata.get('suggested_ticker')
                if suggested_ticker:
                    print(f"   INFO: Suggested ticker in metadata: {suggested_ticker}")
                    # Try to fetch with suggested ticker
                    alt_market = market_data.get_live_price(suggested_ticker)
                    if alt_market and alt_market.get('price', 0) > 0:
                        print(f"   SUCCESS: Suggested ticker WORKS! Price: ${alt_market['price']:.2f}")
                
                problematic_entities.append({
                    'entity_id': entity.entity_id,
                    'entity_name': entity.entity_name,
                    'entity_type': entity.entity_type,
                    'predictions': pred_count,
                    'simulations': sim_count,
                    'suggested_ticker': suggested_ticker
                })
            else:
                price = market_snapshot.get('price', 0)
                print(f"   SUCCESS: Market data available: ${price:.2f}")
        
        print("\n" + "="*80)
        print(f"SUMMARY: Found {len(problematic_entities)} entities without market data")
        print("="*80)
        
        if problematic_entities:
            print("\nPROBLEMATIC ENTITIES:")
            for ent in problematic_entities:
                print(f"\n  • {ent['entity_name']} (ID: {ent['entity_id']})")
                print(f"    Predictions: {ent['predictions']}, Simulations: {ent['simulations']}")
                if ent['suggested_ticker']:
                    print(f"    Suggested ticker: {ent['suggested_ticker']}")
                
                # Check if this entity came from news about another company
                mappings = db.query(NewsEntityMapping).filter(
                    NewsEntityMapping.entity_id == ent['entity_id']
                ).limit(3).all()
                
                if mappings:
                    print(f"    Found in {len(mappings)} news articles:")
                    for mapping in mappings[:3]:
                        news = db.query(RawNews).filter(
                            RawNews.news_id == mapping.news_id
                        ).first()
                        if news:
                            print(f"      - {news.title[:80]}...")
        
        return problematic_entities

if __name__ == "__main__":
    problematic = check_entity_ticker_issues()
    
    if problematic:
        print("\n" + "="*80)
        print("RECOMMENDED ACTIONS:")
        print("="*80)
        print("\n1. For entities with suggested_ticker that works:")
        print("   - Update entity_id to use the suggested_ticker")
        print("   - Update all predictions and simulations to use new entity_id")
        print("\n2. For entities extracted from news about other companies (e.g., 'Oppenheimer' from PNC news):")
        print("   - These are analyst firm names, not tickers")
        print("   - Should not have predictions created for them")
        print("   - Consider filtering these out in entity extraction")
