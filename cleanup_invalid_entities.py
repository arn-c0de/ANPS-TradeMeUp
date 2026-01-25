"""
Cleanup script to remove invalid entities (fallback COMP_ entities and analyst firms)
and their associated predictions and simulations
"""
import logging
from sqlalchemy import or_
from sqlalchemy.orm import Session
from src.models.database import engine
from src.models.entities import Entity, NewsEntityMapping
from src.models.predictions import Prediction
from src.models.trading_simulation import TradingSimulation
from src.models.analysis import ImpactScore

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# List of analyst firms to remove
ANALYST_FIRMS_TO_REMOVE = [
    'COMP_OPPENHEIMER', 'COMP_WELLSFARGO', 'COMP_RBCCAPITAL', 'COMP_TDCOWEN',
    'COMP_SCOTIABANK', 'COMP_JPMORGAN', 'COMP_GOLDMANSACHS', 'COMP_MORGANSTANLEY',
    'COMP_BOFASECURITIES', 'COMP_BARCLAYS', 'COMP_CITI', 'COMP_DEUTSCHEBANK',
    'COMP_CREDITSUI SSE', 'COMP_UBSSECURITIES', 'COMP_JEFFERIES', 'COMP_PIPERSANDLER',
    'COMP_RAYMONDJAMES', 'COMP_STIFEL', 'COMP_EVERCORE', 'COMP_BERNSTEIN',
    'COMP_WEDBUSH', 'COMP_NEEDHAM', 'COMP_TRUIST', 'COMP_KEYBANC', 'COMP_BAIRD',
    'COMP_BMO', 'COMP_BTIG', 'COMP_CANACCORD', 'COMP_MIZUHO', 'COMP_LOOPCAPITAL'
]

# Sectors that shouldn't have predictions
INVALID_SECTORS = ['OTHER', 'HEALTH']

def cleanup_invalid_entities():
    """Remove invalid entities and their associations"""
    with Session(engine) as db:
        print("\n" + "="*80)
        print("CLEANING UP INVALID ENTITIES")
        print("="*80)
        
        # Find all entities that start with COMP_ (fallback entities)
        fallback_entities = db.query(Entity).filter(
            Entity.entity_id.like('COMP_%')
        ).all()
        
        # Find analyst firm entities
        analyst_entities = db.query(Entity).filter(
            Entity.entity_id.in_(ANALYST_FIRMS_TO_REMOVE)
        ).all()
        
        # Find invalid sector entities
        invalid_sector_entities = db.query(Entity).filter(
            or_(
                Entity.entity_id.in_(INVALID_SECTORS),
                Entity.entity_id == 'HEALTH'
            )
        ).all()
        
        all_invalid = fallback_entities + analyst_entities + invalid_sector_entities
        
        if not all_invalid:
            print("\nNo invalid entities found.")
            return
        
        print(f"\nFound {len(all_invalid)} invalid entities:")
        print(f"  - Fallback entities (COMP_*): {len(fallback_entities)}")
        print(f"  - Analyst firms: {len(analyst_entities)}")
        print(f"  - Invalid sectors: {len(invalid_sector_entities)}")
        
        # Count associated records before deletion
        total_predictions = 0
        total_simulations = 0
        total_impacts = 0
        total_mappings = 0
        
        for entity in all_invalid:
            pred_count = db.query(Prediction).filter(
                Prediction.entity_id == entity.entity_id
            ).count()
            sim_count = db.query(TradingSimulation).filter(
                TradingSimulation.entity_id == entity.entity_id
            ).count()
            impact_count = db.query(ImpactScore).filter(
                ImpactScore.entity_id == entity.entity_id
            ).count()
            mapping_count = db.query(NewsEntityMapping).filter(
                NewsEntityMapping.entity_id == entity.entity_id
            ).count()
            
            total_predictions += pred_count
            total_simulations += sim_count
            total_impacts += impact_count
            total_mappings += mapping_count
            
            if pred_count > 0 or sim_count > 0 or impact_count > 0:
                print(f"\n  {entity.entity_name} ({entity.entity_id}):")
                print(f"    - Predictions: {pred_count}")
                print(f"    - Simulations: {sim_count}")
                print(f"    - Impact Scores: {impact_count}")
                print(f"    - News Mappings: {mapping_count}")
        
        print(f"\n" + "="*80)
        print("TOTAL TO DELETE:")
        print(f"  - Predictions: {total_predictions}")
        print(f"  - Simulations: {total_simulations}")
        print(f"  - Impact Scores: {total_impacts}")
        print(f"  - News Mappings: {total_mappings}")
        print(f"  - Entities: {len(all_invalid)}")
        print("="*80)
        
        # Ask for confirmation
        response = input("\nDo you want to delete these records? (yes/no): ")
        
        if response.lower() != 'yes':
            print("Cleanup cancelled.")
            return
        
        print("\nDeleting records...")
        
        # Delete in order (respect foreign key constraints)
        for entity in all_invalid:
            entity_id = entity.entity_id
            
            # Delete simulations first (references predictions)
            sim_deleted = db.query(TradingSimulation).filter(
                TradingSimulation.entity_id == entity_id
            ).delete()
            
            # Delete predictions
            pred_deleted = db.query(Prediction).filter(
                Prediction.entity_id == entity_id
            ).delete()
            
            # Delete impact scores
            impact_deleted = db.query(ImpactScore).filter(
                ImpactScore.entity_id == entity_id
            ).delete()
            
            # Delete news mappings
            mapping_deleted = db.query(NewsEntityMapping).filter(
                NewsEntityMapping.entity_id == entity_id
            ).delete()
            
            # Delete entity
            db.query(Entity).filter(Entity.entity_id == entity_id).delete()
            
            logger.info(f"Deleted {entity.entity_name}: {pred_deleted} predictions, {sim_deleted} simulations, {impact_deleted} impacts, {mapping_deleted} mappings")
        
        # Commit all deletions
        db.commit()
        
        print(f"\n" + "="*80)
        print("CLEANUP COMPLETE")
        print(f"Successfully deleted:")
        print(f"  - {total_predictions} predictions")
        print(f"  - {total_simulations} simulations")
        print(f"  - {total_impacts} impact scores")
        print(f"  - {total_mappings} news mappings")
        print(f"  - {len(all_invalid)} entities")
        print("="*80)

if __name__ == "__main__":
    cleanup_invalid_entities()
