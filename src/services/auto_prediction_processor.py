"""
Automatic Prediction Processor Service

This service automatically processes new predictions by:
1. Calculating performance (PredictionOutcome)
2. Creating trading simulations

Can be called after new predictions are created to ensure they are fully processed.
"""

import logging
from typing import List, Dict
from datetime import datetime

from sqlalchemy.orm import Session, joinedload
from sqlalchemy import func

from src.models.predictions import Prediction, PredictionOutcome
from src.models.trading_simulation import TradingSimulation
from src.models.entities import Entity
from src.services.prediction_performance_service import PredictionPerformanceService
from src.simulations.trading_simulator import TradingSimulationEngine
from src.utils.activity_logger import activity_logger

logger = logging.getLogger(__name__)


class AutoPredictionProcessor:
    """Automatically process new predictions with performance and simulations"""
    
    def __init__(self):
        self.performance_service = PredictionPerformanceService()
        self.sim_engine = TradingSimulationEngine()
    
    def update_all_predictions_for_entity(
        self,
        db: Session,
        entity_id: str
    ) -> Dict:
        """
        Update all predictions for a specific entity/ticker with fresh performance data.
        
        Args:
            db: Database session
            entity_id: Entity ID (ticker) to update
            
        Returns:
            dict: Statistics about updated predictions
        """
        logger.info(f"🔄 Updating all predictions for entity: {entity_id}")
        
        # Find all predictions for this entity
        predictions = db.query(Prediction).filter(
            Prediction.entity_id == entity_id
        ).options(
            joinedload(Prediction.entity),
            joinedload(Prediction.outcome)
        ).all()
        
        if not predictions:
            logger.warning(f"No predictions found for entity: {entity_id}")
            return {
                'entity_id': entity_id,
                'total_found': 0,
                'updated': 0,
                'errors': 0
            }
        
        logger.info(f"📊 Found {len(predictions)} predictions for {entity_id}")
        
        updated = 0
        errors = 0
        
        for pred in predictions:
            try:
                entity = pred.entity
                
                if not entity:
                    logger.warning(f"Prediction {pred.prediction_id} has no entity")
                    continue
                
                # Calculate fresh performance
                performance = self.performance_service.get_prediction_performance(pred, entity)
                
                if performance:
                    # Force current timestamp for batch updates
                    performance['timestamp'] = datetime.now()
                    
                    # Save to database
                    self.performance_service.save_prediction_performance(
                        pred.prediction_id,
                        performance,
                        db
                    )
                    db.commit()
                    
                    total_return = performance.get('total_return_pct', 0)
                    logger.debug(f"Updated {pred.prediction_id}: {total_return:+.2f}% (timestamp: now)")
                    updated += 1
                else:
                    logger.debug(f"Could not calculate performance for {pred.prediction_id}")
            
            except Exception as e:
                logger.error(f"Error updating prediction {pred.prediction_id}: {e}")
                errors += 1
        
        stats = {
            'entity_id': entity_id,
            'total_found': len(predictions),
            'updated': updated,
            'errors': errors
        }
        
        logger.info(f"✅ Updated {updated}/{len(predictions)} predictions for {entity_id}")
        
        return stats
    
    def process_new_predictions(
        self, 
        db: Session, 
        lookback_minutes: int = 60,
        force_recalculate: bool = False
    ) -> Dict:
        """
        Process predictions created in the last N minutes.
        
        Args:
            db: Database session
            lookback_minutes: How far back to look for new predictions
            force_recalculate: If True, recalculate even if data exists
            
        Returns:
            dict: Statistics about processed predictions
        """
        from datetime import timedelta
        
        cutoff_time = datetime.utcnow() - timedelta(minutes=lookback_minutes)
        
        logger.info(f"🔍 Looking for predictions created after {cutoff_time.strftime('%Y-%m-%d %H:%M')}")
        
        # Find recent predictions
        query = db.query(Prediction).filter(
            Prediction.created_at >= cutoff_time
        ).options(
            joinedload(Prediction.entity),
            joinedload(Prediction.outcome)
        ).order_by(Prediction.created_at.desc())
        
        predictions = query.all()
        total_found = len(predictions)
        
        logger.info(f"📊 Found {total_found} recent predictions")
        
        if total_found == 0:
            return {
                'total_found': 0,
                'outcomes_created': 0,
                'simulations_created': 0,
                'errors': 0
            }
        
        outcomes_created = 0
        simulations_created = 0
        errors = 0
        
        for pred in predictions:
            try:
                entity = pred.entity
                
                if not entity:
                    logger.warning(f"⚠️ Prediction {pred.prediction_id} has no entity, skipping")
                    continue
                
                # Check if outcome already exists
                has_outcome = pred.outcome and len(pred.outcome) > 0
                
                if not has_outcome or force_recalculate:
                    logger.info(f"📈 Calculating performance for {entity.entity_name} ({pred.horizon})...")
                    
                    try:
                        # Calculate performance
                        performance = self.performance_service.get_prediction_performance(pred, entity)
                        
                        if performance:
                            # Save to database
                            self.performance_service.save_prediction_performance(
                                pred.prediction_id, 
                                performance, 
                                db
                            )
                            db.commit()
                            
                            total_return = performance.get('total_return_pct', 0)
                            is_correct = performance.get('is_correct', False)
                            logger.info(f"✅ Performance: {total_return:+.2f}% ({'✓' if is_correct else '✗'})")
                            outcomes_created += 1
                        else:
                            logger.debug(f"⚠️ Could not calculate performance for {entity.entity_name}")
                    except Exception as e:
                        logger.warning(f"⚠️ Error calculating performance: {e}")
                
                # Check if simulation already exists
                existing_sim = db.query(TradingSimulation).filter(
                    TradingSimulation.prediction_id == pred.prediction_id
                ).first()
                
                if not existing_sim or force_recalculate:
                    logger.info(f"🧪 Creating simulation for {entity.entity_name} ({pred.horizon})...")
                    
                    try:
                        # Create simulation
                        simulation = self.sim_engine.simulate_prediction(db, pred, entity)
                        
                        if simulation:
                            db.commit()
                            
                            decision = simulation.decision
                            expected_return = simulation.expected_return_pct or 0
                            risk_score = simulation.risk_score or 0
                            logger.info(f"✅ Simulation: {decision.upper()} (Return: {expected_return:+.2f}%, Risk: {risk_score:.2f})")
                            simulations_created += 1
                        else:
                            logger.debug(f"⚠️ Simulation not created for {entity.entity_name}")
                    except Exception as e:
                        logger.warning(f"⚠️ Error creating simulation: {e}")
                
            except Exception as e:
                logger.error(f"❌ Error processing prediction {pred.prediction_id}: {e}")
                errors += 1
        
        stats = {
            'total_found': total_found,
            'outcomes_created': outcomes_created,
            'simulations_created': simulations_created,
            'errors': errors
        }
        
        if outcomes_created > 0 or simulations_created > 0:
            logger.info(f"✅ Auto-processed {total_found} predictions: {outcomes_created} outcomes, {simulations_created} simulations")
            activity_logger.log_activity(
                f"Auto-processed {total_found} predictions: {outcomes_created} outcomes, {simulations_created} simulations",
                "INFO"
            )
        
        return stats
    
    def process_specific_predictions(
        self, 
        db: Session, 
        prediction_ids: List[str]
    ) -> Dict:
        """
        Process specific predictions by ID.
        
        Args:
            db: Database session
            prediction_ids: List of prediction IDs to process
            
        Returns:
            dict: Statistics about processed predictions
        """
        logger.info(f"🔍 Processing {len(prediction_ids)} specific predictions")
        
        outcomes_created = 0
        simulations_created = 0
        errors = 0
        
        for pred_id in prediction_ids:
            try:
                pred = db.query(Prediction).filter(
                    Prediction.prediction_id == pred_id
                ).options(
                    joinedload(Prediction.entity)
                ).first()
                
                if not pred:
                    logger.warning(f"⚠️ Prediction {pred_id} not found")
                    continue
                
                entity = pred.entity
                
                if not entity:
                    logger.warning(f"⚠️ Prediction {pred_id} has no entity")
                    continue
                
                # Calculate performance
                try:
                    performance = self.performance_service.get_prediction_performance(pred, entity)
                    
                    if performance:
                        self.performance_service.save_prediction_performance(
                            pred.prediction_id, 
                            performance, 
                            db
                        )
                        db.commit()
                        outcomes_created += 1
                        logger.info(f"✅ Performance calculated for {entity.entity_name}")
                except Exception as e:
                    logger.warning(f"⚠️ Error calculating performance: {e}")
                
                # Create simulation
                try:
                    simulation = self.sim_engine.simulate_prediction(db, pred, entity)
                    
                    if simulation:
                        db.commit()
                        simulations_created += 1
                        logger.info(f"✅ Simulation created for {entity.entity_name}")
                except Exception as e:
                    logger.warning(f"⚠️ Error creating simulation: {e}")
                
            except Exception as e:
                logger.error(f"❌ Error processing prediction {pred_id}: {e}")
                errors += 1
        
        stats = {
            'total_found': len(prediction_ids),
            'outcomes_created': outcomes_created,
            'simulations_created': simulations_created,
            'errors': errors
        }
        
        logger.info(f"✅ Processed {len(prediction_ids)} predictions: {outcomes_created} outcomes, {simulations_created} simulations")
        
        return stats


# Global instance
auto_processor = AutoPredictionProcessor()
