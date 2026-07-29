"""Agent 12.5: Model Performance Monitor - Track and analyze model performance."""
import logging
from datetime import UTC, datetime, timedelta

import numpy as np
from sqlalchemy.orm import Session

from src.models.predictions import Prediction, PredictionOutcome
from src.utils.prediction_math import (
    FLAT_RETURN_TOLERANCE_PCT,
    get_expected_return_pct,
    get_predicted_direction,
)

logger = logging.getLogger(__name__)


class ModelPerformanceMonitor:
    """
    Agent 12.5: Model Performance Monitor

    Responsibilities:
    - Track model accuracy over time
    - Calculate performance metrics (Sharpe, win rate, etc.)
    - Detect model degradation
    - Generate performance reports
    """

    def __init__(self, db: Session):
        """Initialize model performance monitor."""
        self.db = db

    def calculate_accuracy_metrics(
        self,
        model_version: str = 'xgboost_baseline',
        lookback_days: int = 30
    ) -> dict:
        """
        Calculate comprehensive accuracy metrics for a model.

        Args:
            model_version: Model to analyze
            lookback_days: Historical period

        Returns:
            Performance metrics
        """
        cutoff = datetime.now(UTC) - timedelta(days=lookback_days)

        # Fetch predictions with outcomes
        predictions = self.db.query(Prediction).join(
            PredictionOutcome,
            Prediction.prediction_id == PredictionOutcome.prediction_id
        ).filter(
            Prediction.model_version == model_version,
            Prediction.created_at >= cutoff
        ).all()

        if len(predictions) < 5:
            return {
                'error': 'insufficient_data',
                'prediction_count': len(predictions)
            }

        # Calculate metrics
        correct_predictions = 0
        total_predictions = len(predictions)
        returns = []
        squared_errors = []

        outcomes = self._outcomes_by_prediction(predictions)

        for pred in predictions:
            outcome = outcomes.get(pred.prediction_id)
            if not outcome or outcome.actual_return is None:
                continue

            actual_return = outcome.actual_return

            if self._direction_was_correct(pred, actual_return):
                correct_predictions += 1

            # Return prediction error, both sides in percent
            predicted_return = get_expected_return_pct(pred)
            squared_errors.append((predicted_return - actual_return) ** 2)
            returns.append(actual_return)

        # Calculate metrics
        accuracy = correct_predictions / total_predictions if total_predictions > 0 else 0.0
        rmse = np.sqrt(np.mean(squared_errors)) if squared_errors else 0.0
        mean_return = np.mean(returns) if returns else 0.0
        std_return = np.std(returns) if returns else 0.0
        sharpe = (mean_return / std_return) * np.sqrt(252) if std_return > 0 else 0.0

        return {
            'model_version': model_version,
            'lookback_days': lookback_days,
            'total_predictions': total_predictions,
            'correct_predictions': correct_predictions,
            'accuracy': float(accuracy),
            'rmse': float(rmse),
            'mean_return': float(mean_return),
            'std_return': float(std_return),
            'sharpe_ratio': float(sharpe),
            'win_rate': float(accuracy)
        }

    def detect_model_degradation(
        self,
        model_version: str = 'xgboost_baseline',
        short_window: int = 7,
        long_window: int = 30
    ) -> dict:
        """
        Detect if model performance is degrading.

        Args:
            model_version: Model to monitor
            short_window: Recent performance window
            long_window: Historical baseline window

        Returns:
            Degradation analysis
        """
        # Calculate recent vs historical performance
        recent_metrics = self.calculate_accuracy_metrics(model_version, short_window)
        historical_metrics = self.calculate_accuracy_metrics(model_version, long_window)

        if 'error' in recent_metrics or 'error' in historical_metrics:
            return {
                'degradation_detected': False,
                'reason': 'insufficient_data'
            }

        # Compare metrics
        accuracy_drop = historical_metrics['accuracy'] - recent_metrics['accuracy']
        rmse_increase = recent_metrics['rmse'] - historical_metrics['rmse']

        # Thresholds for degradation
        degradation_detected = (
            accuracy_drop > 0.1 or  # >10% accuracy drop
            rmse_increase > 0.05    # >5% RMSE increase
        )

        return {
            'degradation_detected': degradation_detected,
            'recent_accuracy': recent_metrics['accuracy'],
            'historical_accuracy': historical_metrics['accuracy'],
            'accuracy_drop': float(accuracy_drop),
            'recent_rmse': recent_metrics['rmse'],
            'historical_rmse': historical_metrics['rmse'],
            'rmse_increase': float(rmse_increase),
            'severity': 'high' if accuracy_drop > 0.15 else 'medium' if accuracy_drop > 0.1 else 'low'
        }

    def generate_performance_report(
        self,
        model_version: str = 'xgboost_baseline'
    ) -> dict:
        """
        Generate comprehensive performance report.

        Args:
            model_version: Model to report on

        Returns:
            Performance report
        """
        # Different time windows
        metrics_7d = self.calculate_accuracy_metrics(model_version, 7)
        metrics_30d = self.calculate_accuracy_metrics(model_version, 30)
        metrics_90d = self.calculate_accuracy_metrics(model_version, 90)

        # Degradation check
        degradation = self.detect_model_degradation(model_version)

        # By horizon breakdown
        by_horizon = self._calculate_by_horizon(model_version)

        return {
            'model_version': model_version,
            'generated_at': datetime.now(UTC).isoformat(),
            'performance_7d': metrics_7d,
            'performance_30d': metrics_30d,
            'performance_90d': metrics_90d,
            'degradation_analysis': degradation,
            'by_horizon': by_horizon
        }

    def _calculate_by_horizon(self, model_version: str) -> dict:
        """Calculate performance by prediction horizon."""
        horizons = ['1d', '5d', '20d']
        by_horizon = {}

        for horizon in horizons:
            predictions = self.db.query(Prediction).join(
                PredictionOutcome,
                Prediction.prediction_id == PredictionOutcome.prediction_id
            ).filter(
                Prediction.model_version == model_version,
                Prediction.horizon == horizon
            ).limit(100).all()

            if len(predictions) < 5:
                by_horizon[horizon] = {'error': 'insufficient_data'}
                continue

            outcomes = self._outcomes_by_prediction(predictions)

            scored = 0
            correct = 0
            for pred in predictions:
                outcome = outcomes.get(pred.prediction_id)
                if not outcome or outcome.actual_return is None:
                    continue

                scored += 1
                if self._direction_was_correct(pred, outcome.actual_return):
                    correct += 1

            by_horizon[horizon] = {
                # Divide by the number actually scored, not by every prediction
                # fetched: predictions without a usable outcome would otherwise
                # be counted as wrong.
                'accuracy': correct / scored if scored else 0.0,
                'sample_count': scored
            }

        return by_horizon

    def _outcomes_by_prediction(self, predictions: list[Prediction]) -> dict:
        """Fetch all outcomes for ``predictions`` in a single query.

        Looking each outcome up inside the loop issued one query per
        prediction, on top of the join that already selected them.
        """
        if not predictions:
            return {}

        prediction_ids = [pred.prediction_id for pred in predictions]
        rows = self.db.query(PredictionOutcome).filter(
            PredictionOutcome.prediction_id.in_(prediction_ids)
        ).all()
        return {row.prediction_id: row for row in rows}

    @staticmethod
    def _direction_was_correct(prediction: Prediction, actual_return_pct: float) -> bool:
        """Whether the predicted direction matched the realised move."""
        predicted_dir = get_predicted_direction(prediction)

        if predicted_dir == 'up':
            return actual_return_pct > 0
        if predicted_dir == 'down':
            return actual_return_pct < 0
        return abs(actual_return_pct) < FLAT_RETURN_TOLERANCE_PCT

    def process_batch(self, limit: int = 5) -> dict:
        """
        Generate performance reports for all models.

        Args:
            limit: Max models to analyze

        Returns:
            Statistics
        """
        # Get unique model versions
        model_versions = self.db.query(Prediction.model_version).distinct().limit(limit).all()

        logger.info(f"Analyzing performance for {len(model_versions)} models")

        stats = {
            'models_analyzed': 0,
            'reports': []
        }

        for (model_version,) in model_versions:
            try:
                report = self.generate_performance_report(model_version)
                stats['reports'].append(report)
                stats['models_analyzed'] += 1

            except Exception as e:
                logger.error(f"Error analyzing model {model_version}: {e}")

        logger.info(f"Performance monitoring complete. Stats: {stats}")
        return stats

    def get_statistics(self) -> dict:
        """Get performance monitoring statistics."""
        total_models = self.db.query(Prediction.model_version).distinct().count()

        return {
            'total_models': total_models,
            'available_metrics': [
                'accuracy', 'rmse', 'sharpe_ratio', 'win_rate'
            ]
        }
