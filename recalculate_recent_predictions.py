"""
Quick Script: Recalculate predictions for recent high-impact news
Useful when pipeline is running but no new predictions are created
"""
import sys
from pathlib import Path
from datetime import datetime, timedelta

# Add project root to path
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

from sqlalchemy import create_engine
from sqlalchemy.orm import Session
from src.models.analysis import ImpactScore
from src.models.predictions import Prediction
from src.config.settings import settings
from src.agents.prediction_agent import PredictionAgent

import logging

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


def recalculate_recent_predictions(hours_back: int = 1, min_impact: float = 0.3, force: bool = True):
    """
    Recalculate predictions for recent impact scores.
    
    Args:
        hours_back: How many hours back to look
        min_impact: Minimum impact score threshold
        force: If True, delete existing predictions and recreate them
    """
    engine = create_engine(settings.database_url)
    
    with Session(engine) as db:
        # Get recent impact scores
        cutoff_time = datetime.utcnow() - timedelta(hours=hours_back)
        
        recent_impacts = db.query(ImpactScore).filter(
            ImpactScore.created_at >= cutoff_time,
            ImpactScore.impact_score >= min_impact
        ).order_by(ImpactScore.created_at.desc()).all()
        
        logger.info(f"Found {len(recent_impacts)} impact scores from last {hours_back} hour(s)")
        logger.info(f"Impact threshold: >= {min_impact}")
        
        if not recent_impacts:
            logger.warning("No recent impact scores found. Pipeline may not be creating impact scores.")
            logger.info("Try running: python scripts/run_continuous_pipeline.py")
            return
        
        # Show sample
        logger.info("\nSample impact scores:")
        for imp in recent_impacts[:5]:
            logger.info(f"  {imp.entity_id} | score: {imp.impact_score:.2f} | created: {imp.created_at}")
        
        if force:
            # Delete ONLY predictions that match EXACTLY this news_id
            # NOT all predictions for the entity (that was too aggressive!)
            from src.models.predictions import PredictionOutcome
            
            deleted_predictions = 0
            deleted_outcomes = 0
            
            for impact in recent_impacts:
                news_id_str = str(impact.news_id)
                
                # Get ALL predictions for this entity
                preds_for_entity = db.query(Prediction).filter(
                    Prediction.entity_id == impact.entity_id
                ).all()
                
                # Only delete predictions that have EXACTLY this news_id in their list
                # AND have ONLY this news_id (single-news predictions from this impact)
                for pred in preds_for_entity:
                    if (pred.related_news_ids and 
                        news_id_str in pred.related_news_ids and
                        len(pred.related_news_ids) == 1):  # Only delete if this is the only news
                        
                        # First delete related outcomes
                        outcomes = db.query(PredictionOutcome).filter(
                            PredictionOutcome.prediction_id == pred.prediction_id
                        ).all()
                        for outcome in outcomes:
                            db.delete(outcome)
                            deleted_outcomes += 1
                        
                        # Then delete prediction
                        db.delete(pred)
                        deleted_predictions += 1
            
            db.commit()
            logger.info(f"\n✓ Deleted {deleted_predictions} predictions and {deleted_outcomes} outcomes")
            logger.info(f"   (Only single-news predictions to avoid over-deletion)")
        
        # Create prediction agent
        agent = PredictionAgent()
        
        logger.info("\n🔮 Generating new predictions...")
        logger.info("="*60)
        
        total_created = 0
        horizons = ['1d', '5d', '20d']
        
        # Process each impact score
        for i, impact in enumerate(recent_impacts, 1):
            try:
                logger.info(f"\n[{i}/{len(recent_impacts)}] Processing {impact.entity_id} (score: {impact.impact_score:.2f})")
                
                # Generate predictions for all horizons
                for horizon in horizons:
                    result = agent.generate_prediction(
                        entity_id=impact.entity_id,
                        news_id=str(impact.news_id),
                        horizon=horizon
                    )
                    
                    if result:
                        total_created += 1
                        # Access probabilities immediately before session closes
                        probs = result.direction_probabilities
                        conf = result.confidence
                        logger.info(f"  ✓ {horizon}: up={probs['up']:.2f}, down={probs['down']:.2f}, flat={probs['flat']:.2f} | conf={conf:.2f}")
                    else:
                        logger.warning(f"  ✗ Failed to create prediction for {horizon}")
                
            except Exception as e:
                logger.error(f"Error processing {impact.entity_id}: {e}")
                continue
        
        logger.info("\n" + "="*60)
        logger.info(f"✓ Created {total_created} new predictions")
        logger.info(f"  ({total_created // 3} entities × 3 horizons)")


if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(description="Recalculate predictions for recent impact scores")
    parser.add_argument("--hours", type=int, default=1, help="Look back N hours (default: 1)")
    parser.add_argument("--min-impact", type=float, default=0.3, help="Minimum impact score (default: 0.3)")
    parser.add_argument("--no-force", action="store_true", help="Don't delete existing predictions")
    
    args = parser.parse_args()
    
    print("\n" + "="*80)
    print("  TradeMeUp - Recalculate Recent Predictions")
    print("="*80)
    print(f"Looking back: {args.hours} hour(s)")
    print(f"Min impact: {args.min_impact}")
    print(f"Force recreate: {not args.no_force}")
    if not args.no_force:
        print("\n⚠️  WARNING: This will DELETE existing predictions for these news!")
        print("   (Only single-news predictions to prevent data loss)")
    print("="*80 + "\n")
    
    recalculate_recent_predictions(
        hours_back=args.hours,
        min_impact=args.min_impact,
        force=not args.no_force
    )
    
    print("\n✓ Done!")
