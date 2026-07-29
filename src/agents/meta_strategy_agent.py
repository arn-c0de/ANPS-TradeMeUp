"""Agent 7: Meta-Strategy Agent - Ensemble predictions from multiple models."""
import logging
from collections import defaultdict
from datetime import UTC, datetime, timedelta

from sqlalchemy import func

from src.models.database import SessionLocal
from src.models.entities import Entity, NewsEntityMapping
from src.models.predictions import Prediction, PredictionOutcome
from src.utils.prediction_math import direction_was_correct

logger = logging.getLogger(__name__)

# Used when there is no scored history to rank models by.
DEFAULT_MODEL_WEIGHTS = {'xgboost_baseline': 1.0}

# How far back to look for the per-model predictions that make up an ensemble.
ENSEMBLE_LOOKBACK_HOURS = 24

ENSEMBLE_MODEL_VERSION = 'meta_ensemble'


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
        try:
            with SessionLocal() as db:
                cutoff = datetime.now(UTC) - timedelta(days=lookback_days)

                # Select prediction and outcome together: the previous version
                # joined to filter, then re-queried the outcome once per row.
                rows = db.query(Prediction, PredictionOutcome).join(
                    PredictionOutcome,
                    Prediction.prediction_id == PredictionOutcome.prediction_id
                ).filter(
                    Prediction.created_at >= cutoff
                ).all()

            if not rows:
                # Default equal weights
                return DEFAULT_MODEL_WEIGHTS.copy()

            # Accuracy per model, as hits / scored
            hits: dict[str, int] = defaultdict(int)
            scored: dict[str, int] = defaultdict(int)

            for prediction, outcome in rows:
                model_id = prediction.model_version
                scored[model_id] += 1
                if direction_was_correct(prediction, outcome.actual_return):
                    hits[model_id] += 1

            accuracies = {
                model_id: hits[model_id] / count
                for model_id, count in scored.items()
                if count > 0
            }

            # Normalise accuracies into weights that sum to 1. If every model
            # scored zero there is nothing to rank them by, so fall back.
            total = sum(accuracies.values())
            if total <= 0:
                return DEFAULT_MODEL_WEIGHTS.copy()

            weights = {model_id: acc / total for model_id, acc in accuracies.items()}

            self._model_weights = weights
            logger.info(f"Calculated model weights: {weights}")

            return weights
        except Exception as e:
            logger.error(f"Error calculating model weights: {e}")
            return DEFAULT_MODEL_WEIGHTS.copy()

    @staticmethod
    def _aggregate(
        model_predictions: list[Prediction], weights: dict[str, float]
    ) -> tuple[float, float, dict[str, float]]:
        """Combine per-model predictions into (return, confidence, direction probabilities)."""
        # A model with no measured history still gets a say, at the weight it
        # would have if every prediction here were equally trusted.
        fallback_weight = 1.0 / len(model_predictions)

        ensemble_return = 0.0
        ensemble_confidence = 0.0
        direction_votes = {'up': 0.0, 'down': 0.0, 'flat': 0.0}

        for pred in model_predictions:
            weight = weights.get(pred.model_version, fallback_weight)

            ensemble_return += pred.predicted_return * weight
            ensemble_confidence += pred.confidence * weight

            # Unknown directions are ignored rather than raising: the stored
            # probabilities are free-form JSON and may carry other keys.
            if pred.predicted_direction in direction_votes:
                direction_votes[pred.predicted_direction] += weight

        total_votes = sum(direction_votes.values())
        if total_votes > 0:
            probabilities = {d: v / total_votes for d, v in direction_votes.items()}
        else:
            # No usable direction anywhere - say so instead of dividing by zero.
            probabilities = {'up': 1 / 3, 'down': 1 / 3, 'flat': 1 / 3}

        return ensemble_return, ensemble_confidence, probabilities

    def create_ensemble_prediction(
        self,
        entity_id: str,
        horizon: str = '1d',
        weights: dict[str, float] | None = None,
    ) -> Prediction | None:
        """
        Create ensemble prediction from multiple models.

        Args:
            entity_id: Entity to predict for
            horizon: Prediction horizon
            weights: Pre-computed output of :meth:`calculate_model_weights`. Pass
                it when building many ensembles - recomputing it per entity
                re-scans the full lookback window every single time.

        Returns:
            Ensemble prediction
        """
        if weights is None:
            weights = self.calculate_model_weights()

        try:
            with SessionLocal() as db:
                cutoff = datetime.now(UTC) - timedelta(hours=ENSEMBLE_LOOKBACK_HOURS)

                model_predictions = db.query(Prediction).filter(
                    Prediction.entity_id == entity_id,
                    Prediction.horizon == horizon,
                    Prediction.created_at >= cutoff,
                    Prediction.model_version != ENSEMBLE_MODEL_VERSION,
                ).all()

                if not model_predictions:
                    logger.warning(f"No predictions found for {entity_id}")
                    return None

                ensemble_return, ensemble_confidence, probabilities = self._aggregate(
                    model_predictions, weights
                )

                now = datetime.now(UTC)
                ensemble = Prediction(
                    entity_id=entity_id,
                    horizon=horizon,
                    timestamp=now,
                    model_version=ENSEMBLE_MODEL_VERSION,
                    direction_probabilities=probabilities,
                    expected_return={
                        'mean': ensemble_return,
                        'median': ensemble_return,
                        'p25': ensemble_return * 0.8,
                        'p75': ensemble_return * 1.2,
                        'p95': ensemble_return * 1.5,
                        # predicted_return is already a percentage, so record
                        # that rather than leaving it to the format heuristic.
                        'is_percentage': True,
                    },
                    confidence=ensemble_confidence,
                    model_contributions={'model_weights': weights},
                    created_at=now
                )

                db.add(ensemble)
                db.commit()
                db.refresh(ensemble)
                db.expunge(ensemble)

            logger.info(
                f"Created ensemble prediction for {entity_id}: "
                f"{max(probabilities, key=probabilities.get)} ({ensemble_return:.4f})"
            )
            return ensemble
        except Exception as e:
            logger.error(f"Error creating ensemble prediction for {entity_id}: {e}")
            return None

    def process_batch(self, limit: int = 10) -> dict:
        """
        Create ensemble predictions for top entities.

        Args:
            limit: Number of entities to process

        Returns:
            Statistics
        """
        stats = {'processed': 0, 'skipped': 0, 'errors': 0}

        try:
            with SessionLocal() as db:
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

            # Computed once for the whole batch. Letting each call recompute it
            # re-ran a 30-day scan per entity.
            weights = self.calculate_model_weights()

            for (entity_id,) in top_entities:
                # An entity with no recent per-model predictions is skipped,
                # not failed - there is simply nothing to ensemble yet.
                if self.create_ensemble_prediction(entity_id, '1d', weights=weights):
                    stats['processed'] += 1
                else:
                    stats['skipped'] += 1

            logger.info(f"Ensemble creation complete. Stats: {stats}")
            return stats
        except Exception as e:
            logger.error(f"Error in process_batch: {e}")
            return {'processed': 0, 'errors': 1, 'error': str(e)}

    def get_statistics(self) -> dict:
        """Get meta-strategy statistics."""
        try:
            with SessionLocal() as db:
                ensemble_count = db.query(Prediction).filter(
                    Prediction.model_version == ENSEMBLE_MODEL_VERSION
                ).count()

            return {
                'ensemble_predictions': ensemble_count,
                'current_model_weights': self._model_weights or self.calculate_model_weights()
            }
        except Exception as e:
            logger.error(f"Error getting statistics: {e}")
            return {'ensemble_predictions': 0, 'current_model_weights': {}}
