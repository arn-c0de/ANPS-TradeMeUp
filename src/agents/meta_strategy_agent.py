"""Agent 7: Meta-Strategy Agent - Ensemble predictions from multiple models."""
import logging
from datetime import UTC, datetime, timedelta, timezone
from typing import Dict, List, Optional

import numpy as np
from sqlalchemy.orm import Session

from src.models.database import SessionLocal
from src.models.entities import Entity
from src.models.predictions import Prediction
from src.utils.json_helpers import ensure_dict

logger = logging.getLogger(__name__)


class MetaStrategyAgent:
    """
    Agent 7: Meta-Strategy Agent

    Responsibilities:
    - Ensemble predictions from multiple models
    - Weight models by historical performance
    - Provide final aggregated predictions
    - Track ensemble performance
    """

    def __init__(self):
        """
        Initialize meta-strategy agent.
        
        Note: Uses scoped sessions internally for better isolation.
        """
        self._model_weights = {}

    def calculate_model_weights(self, lookback_days: int = 30) -> dict[str, float]:
        """
        Calculate weights for each model based on historical performance.

        Args:
            lookback_days: Historical period to evaluate

        Returns:
            Dictionary of model_id -> weight
        """
        from datetime import timedelta

        from src.models.predictions import PredictionOutcome

        db = SessionLocal()
        try:
            cutoff = datetime.now(UTC) - timedelta(days=lookback_days)

            # Get all predictions with outcomes
            predictions = db.query(Prediction).join(
                PredictionOutcome,
                Prediction.prediction_id == PredictionOutcome.prediction_id
            ).filter(
                Prediction.created_at >= cutoff
            ).all()

            if not predictions:
                # Default equal weights
                return {'xgboost_baseline': 1.0}

            # Calculate accuracy by model
            model_accuracies = {}
            model_counts = {}

            for pred in predictions:
                model_id = pred.model_version
                outcome = db.query(PredictionOutcome).filter(
                    PredictionOutcome.prediction_id == pred.prediction_id
                ).first()

                if not outcome:
                    continue

                # Check accuracy
                correct = self._check_accuracy(pred, outcome)

                if model_id not in model_accuracies:
                    model_accuracies[model_id] = 0
                    model_counts[model_id] = 0

                model_accuracies[model_id] += (1 if correct else 0)
                model_counts[model_id] += 1

            # Calculate accuracy ratios
            accuracies = {}
            for model_id in model_accuracies:
                if model_counts[model_id] > 0:
                    accuracies[model_id] = model_accuracies[model_id] / model_counts[model_id]

            if not accuracies:
                return {'xgboost_baseline': 1.0}

            # Convert to weights (softmax)
            total = sum(accuracies.values())
            weights = {m: acc / total for m, acc in accuracies.items()}

            self._model_weights = weights
            logger.info(f"Calculated model weights: {weights}")

            return weights
        except Exception as e:
            logger.error(f"Error calculating model weights: {e}")
            return {'xgboost_baseline': 1.0}
        finally:
            db.close()

    def _check_accuracy(self, prediction: Prediction, outcome) -> bool:
        """Check if prediction was correct."""
        # Extract predicted direction from direction_probabilities
        probs = ensure_dict(prediction.direction_probabilities, {})
        predicted_dir = max(probs, key=probs.get) if probs else 'flat'

        actual_return = outcome.actual_return

        if predicted_dir == 'up':
            return actual_return > 0
        elif predicted_dir == 'down':
            return actual_return < 0
        else:
            return abs(actual_return) < 0.01

    def create_ensemble_prediction(
        self,
        entity_id: str,
        horizon: str = '1d'
    ) -> Prediction | None:
        """
        Create ensemble prediction from multiple models.

        Args:
            entity_id: Entity to predict for
            horizon: Prediction horizon

        Returns:
            Ensemble prediction
        """
        db = SessionLocal()
        try:
            # Get recent predictions from all models
            cutoff = datetime.now(UTC) - timedelta(hours=24)

            model_predictions = db.query(Prediction).filter(
                Prediction.entity_id == entity_id,
                Prediction.horizon == horizon,
                Prediction.created_at >= cutoff
            ).all()

            if not model_predictions:
                logger.warning(f"No predictions found for {entity_id}")
                return None

            # Get model weights
            weights = self.calculate_model_weights()

            # Weighted average of predictions
            weighted_returns = []
            weighted_confidences = []
            direction_votes = {'up': 0, 'down': 0, 'flat': 0}

            for pred in model_predictions:
                model_id = pred.model_version
                weight = weights.get(model_id, 1.0 / len(model_predictions))

                weighted_returns.append(pred.predicted_return * weight)
                weighted_confidences.append(pred.confidence * weight)
                direction_votes[pred.predicted_direction] += weight

            # Aggregate
            ensemble_return = sum(weighted_returns)
            ensemble_confidence = sum(weighted_confidences)
            ensemble_direction = max(direction_votes, key=direction_votes.get)

            # Create ensemble prediction
            ensemble = Prediction(
                entity_id=entity_id,
                horizon=horizon,
                timestamp=datetime.now(UTC),
                model_version='meta_ensemble',
                direction_probabilities={
                    'up': direction_votes['up'] / sum(direction_votes.values()),
                    'down': direction_votes['down'] / sum(direction_votes.values()),
                    'flat': direction_votes['flat'] / sum(direction_votes.values())
                },
                expected_return={
                    'mean': ensemble_return,
                    'median': ensemble_return,
                    'p25': ensemble_return * 0.8,
                    'p75': ensemble_return * 1.2,
                    'p95': ensemble_return * 1.5
                },
                confidence=ensemble_confidence,
                model_contributions={'model_weights': weights},
                created_at=datetime.now(UTC)
            )

            db.add(ensemble)
            db.commit()
            db.refresh(ensemble)

            logger.info(
                f"Created ensemble prediction for {entity_id}: "
                f"{ensemble_direction} ({ensemble_return:.4f})"
            )

            return ensemble
        except Exception as e:
            db.rollback()
            logger.error(f"Error creating ensemble prediction for {entity_id}: {e}")
            return None
        finally:
            db.close()

    def process_batch(self, limit: int = 10) -> dict:
        """
        Create ensemble predictions for top entities.

        Args:
            limit: Number of entities to process

        Returns:
            Statistics
        """
        from sqlalchemy import func

        from src.models.entities import NewsEntityMapping

        db = SessionLocal()
        try:
            # Get top entities
            top_entities = db.query(
                NewsEntityMapping.entity_id
            ).join(
                Entity,
                NewsEntityMapping.entity_id == Entity.entity_id
            ).filter(
                Entity.entity_type == 'company'
            ).group_by(
                NewsEntityMapping.entity_id
            ).order_by(
                func.count(NewsEntityMapping.mapping_id).desc()
            ).limit(limit).all()

            logger.info(f"Creating ensemble predictions for {len(top_entities)} entities")

            stats = {
                'processed': 0,
                'errors': 0
            }

            for (entity_id,) in top_entities:
                try:
                    self.create_ensemble_prediction(entity_id, '1d')
                    stats['processed'] += 1
                except Exception as e:
                    stats['errors'] += 1
                    logger.error(f"Error creating ensemble for {entity_id}: {e}")

            logger.info(f"Ensemble creation complete. Stats: {stats}")
            return stats
        except Exception as e:
            logger.error(f"Error in process_batch: {e}")
            return {'processed': 0, 'errors': 1, 'error': str(e)}
        finally:
            db.close()

    def get_statistics(self) -> dict:
        """Get meta-strategy statistics."""
        db = SessionLocal()
        try:
            ensemble_count = db.query(Prediction).filter(
                Prediction.model_version == 'meta_ensemble'
            ).count()

            return {
                'ensemble_predictions': ensemble_count,
                'current_model_weights': self._model_weights or self.calculate_model_weights()
            }
        except Exception as e:
            logger.error(f"Error getting statistics: {e}")
            return {'ensemble_predictions': 0, 'current_model_weights': {}}
        finally:
            db.close()
