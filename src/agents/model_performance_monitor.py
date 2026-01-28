"""Agent 12.5: Model Performance Monitor - Track and analyze model performance."""
import logging
from typing import Dict, List, Optional
from datetime import datetime, timedelta, timezone
from sqlalchemy.orm import Session
from sqlalchemy import func
import numpy as np

from src.models.predictions import Prediction, PredictionOutcome

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
    ) -> Dict:
        """
        Calculate comprehensive accuracy metrics for a model.

        Args:
            model_version: Model to analyze
            lookback_days: Historical period

        Returns:
            Performance metrics
        """
        cutoff = datetime.now(timezone.utc) - timedelta(days=lookback_days)

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

        for pred in predictions:
            outcome = self.db.query(PredictionOutcome).filter(
                PredictionOutcome.prediction_id == pred.prediction_id
            ).first()

            if not outcome:
                continue

            # Direction accuracy
            predicted_dir = pred.predicted_direction
            actual_return = outcome.actual_return

            if predicted_dir == 'up' and actual_return > 0:
                correct_predictions += 1
            elif predicted_dir == 'down' and actual_return < 0:
                correct_predictions += 1
            elif predicted_dir == 'flat' and abs(actual_return) < 0.01:
                correct_predictions += 1

            # Return prediction error
            predicted_return = pred.predicted_return
            error = (predicted_return - actual_return) ** 2
            squared_errors.append(error)
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
    ) -> Dict:
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
    ) -> Dict:
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
            'generated_at': datetime.now(timezone.utc).isoformat(),
            'performance_7d': metrics_7d,
            'performance_30d': metrics_30d,
            'performance_90d': metrics_90d,
            'degradation_analysis': degradation,
            'by_horizon': by_horizon
        }

    def _calculate_by_horizon(self, model_version: str) -> Dict:
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

            correct = 0
            for pred in predictions:
                outcome = self.db.query(PredictionOutcome).filter(
                    PredictionOutcome.prediction_id == pred.prediction_id
                ).first()

                if outcome:
                    predicted_dir = pred.predicted_direction
                    actual_return = outcome.actual_return

                    if predicted_dir == 'up' and actual_return > 0:
                        correct += 1
                    elif predicted_dir == 'down' and actual_return < 0:
                        correct += 1
                    elif predicted_dir == 'flat' and abs(actual_return) < 0.01:
                        correct += 1

            by_horizon[horizon] = {
                'accuracy': correct / len(predictions),
                'sample_count': len(predictions)
            }

        return by_horizon

    def process_batch(self, limit: int = 5) -> Dict:
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

    def get_statistics(self) -> Dict:
        """Get performance monitoring statistics."""
        total_models = self.db.query(Prediction.model_version).distinct().count()

        return {
            'total_models': total_models,
            'available_metrics': [
                'accuracy', 'rmse', 'sharpe_ratio', 'win_rate'
            ]
        }
