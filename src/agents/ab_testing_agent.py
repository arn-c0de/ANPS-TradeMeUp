"""Agent 13: A/B Testing Framework - Test and compare model variants."""
import logging
from typing import Dict, List, Optional
from datetime import datetime, timedelta, timezone
from sqlalchemy.orm import Session
from sqlalchemy import func
import numpy as np

from src.models.predictions import Prediction, PredictionOutcome

logger = logging.getLogger(__name__)


class ABTestingAgent:
    """
    Agent 13: A/B Testing Framework

    Responsibilities:
    - Run A/B tests between model variants
    - Statistical significance testing
    - Traffic splitting and allocation
    - Test result analysis
    """

    def __init__(self, db: Session):
        """Initialize A/B testing agent."""
        self.db = db
        self._active_tests = {}

    def create_ab_test(
        self,
        test_name: str,
        model_a: str,
        model_b: str,
        traffic_split: float = 0.5,
        duration_days: int = 30
    ) -> Dict:
        """
        Create a new A/B test.

        Args:
            test_name: Name of the test
            model_a: Control model ID
            model_b: Variant model ID
            traffic_split: Percentage of traffic to model_b (0-1)
            duration_days: Test duration in days

        Returns:
            Test configuration
        """
        test_config = {
            'test_id': f"test_{test_name}_{datetime.now(timezone.utc).timestamp()}",
            'test_name': test_name,
            'model_a': model_a,
            'model_b': model_b,
            'traffic_split': traffic_split,
            'start_date': datetime.now(timezone.utc),
            'end_date': datetime.now(timezone.utc) + timedelta(days=duration_days),
            'status': 'active'
        }

        self._active_tests[test_config['test_id']] = test_config

        logger.info(
            f"Created A/B test: {test_name} - "
            f"{model_a} vs {model_b} ({traffic_split*100:.0f}% split)"
        )

        return test_config

    def analyze_ab_test(
        self,
        model_a: str,
        model_b: str,
        lookback_days: int = 30
    ) -> Dict:
        """
        Analyze A/B test results.

        Args:
            model_a: Control model
            model_b: Variant model
            lookback_days: Period to analyze

        Returns:
            Test results with statistical significance
        """
        cutoff = datetime.now(timezone.utc) - timedelta(days=lookback_days)

        # Get predictions for both models
        predictions_a = self.db.query(Prediction).join(
            PredictionOutcome,
            Prediction.prediction_id == PredictionOutcome.prediction_id
        ).filter(
            Prediction.model_id == model_a,
            Prediction.created_at >= cutoff
        ).all()

        predictions_b = self.db.query(Prediction).join(
            PredictionOutcome,
            Prediction.prediction_id == PredictionOutcome.prediction_id
        ).filter(
            Prediction.model_id == model_b,
            Prediction.created_at >= cutoff
        ).all()

        if len(predictions_a) < 20 or len(predictions_b) < 20:
            return {
                'error': 'insufficient_data',
                'sample_a': len(predictions_a),
                'sample_b': len(predictions_b)
            }

        # Calculate metrics for both
        metrics_a = self._calculate_metrics(predictions_a)
        metrics_b = self._calculate_metrics(predictions_b)

        # Statistical significance test (t-test)
        significance = self._test_significance(
            metrics_a['accuracies'],
            metrics_b['accuracies']
        )

        # Determine winner
        winner = None
        if significance['significant']:
            if metrics_b['accuracy'] > metrics_a['accuracy']:
                winner = model_b
            else:
                winner = model_a

        return {
            'model_a': model_a,
            'model_b': model_b,
            'lookback_days': lookback_days,
            'metrics_a': {
                'accuracy': metrics_a['accuracy'],
                'sample_size': metrics_a['sample_size']
            },
            'metrics_b': {
                'accuracy': metrics_b['accuracy'],
                'sample_size': metrics_b['sample_size']
            },
            'improvement': metrics_b['accuracy'] - metrics_a['accuracy'],
            'improvement_pct': ((metrics_b['accuracy'] - metrics_a['accuracy']) / metrics_a['accuracy'] * 100) if metrics_a['accuracy'] > 0 else 0,
            'statistical_significance': significance,
            'winner': winner,
            'confidence_level': significance.get('confidence_level', 0.0)
        }

    def _calculate_metrics(self, predictions: List[Prediction]) -> Dict:
        """Calculate metrics for a set of predictions."""
        correct = 0
        accuracies = []

        for pred in predictions:
            outcome = self.db.query(PredictionOutcome).filter(
                PredictionOutcome.prediction_id == pred.prediction_id
            ).first()

            if not outcome:
                continue

            predicted_dir = pred.predicted_direction
            actual_return = outcome.actual_return

            is_correct = False
            if predicted_dir == 'up' and actual_return > 0:
                is_correct = True
            elif predicted_dir == 'down' and actual_return < 0:
                is_correct = True
            elif predicted_dir == 'flat' and abs(actual_return) < 0.01:
                is_correct = True

            if is_correct:
                correct += 1
                accuracies.append(1)
            else:
                accuracies.append(0)

        return {
            'accuracy': correct / len(predictions) if predictions else 0.0,
            'sample_size': len(predictions),
            'accuracies': accuracies
        }

    def _test_significance(
        self,
        sample_a: List[float],
        sample_b: List[float],
        alpha: float = 0.05
    ) -> Dict:
        """
        Perform t-test for statistical significance.

        Args:
            sample_a: Control group results
            sample_b: Variant group results
            alpha: Significance level

        Returns:
            Significance test results
        """
        from scipy import stats

        try:
            # Two-sample t-test
            t_stat, p_value = stats.ttest_ind(sample_a, sample_b)

            is_significant = p_value < alpha
            confidence_level = (1 - p_value) * 100

            return {
                'significant': is_significant,
                'p_value': float(p_value),
                't_statistic': float(t_stat),
                'confidence_level': float(confidence_level),
                'alpha': alpha
            }

        except Exception as e:
            logger.error(f"Error in significance testing: {e}")
            return {
                'significant': False,
                'error': str(e)
            }

    def recommend_model(
        self,
        model_a: str,
        model_b: str,
        min_improvement: float = 0.05
    ) -> Dict:
        """
        Recommend which model to use based on A/B test.

        Args:
            model_a: Control model
            model_b: Variant model
            min_improvement: Minimum improvement threshold

        Returns:
            Recommendation
        """
        results = self.analyze_ab_test(model_a, model_b, lookback_days=30)

        if 'error' in results:
            return {
                'recommendation': 'continue_testing',
                'reason': results['error']
            }

        improvement = results['improvement']
        is_significant = results['statistical_significance'].get('significant', False)

        if is_significant and improvement >= min_improvement:
            return {
                'recommendation': 'use_model_b',
                'model_recommended': model_b,
                'improvement': improvement,
                'confidence': results['confidence_level']
            }
        elif is_significant and improvement <= -min_improvement:
            return {
                'recommendation': 'use_model_a',
                'model_recommended': model_a,
                'improvement': improvement,
                'confidence': results['confidence_level']
            }
        else:
            return {
                'recommendation': 'continue_testing',
                'reason': 'no_significant_difference',
                'improvement': improvement
            }

    def process_batch(self, limit: int = 5) -> Dict:
        """
        Analyze active A/B tests.

        Args:
            limit: Number of tests to analyze

        Returns:
            Statistics
        """
        # Get unique model pairs
        model_pairs = self.db.query(
            Prediction.model_id
        ).distinct().limit(limit).all()

        if len(model_pairs) < 2:
            logger.warning("Not enough models for A/B testing")
            return {'error': 'insufficient_models'}

        logger.info("Analyzing A/B test results")

        stats = {
            'tests_analyzed': 0,
            'results': []
        }

        # Compare first model with others
        base_model = model_pairs[0][0]

        for (variant_model,) in model_pairs[1:]:
            try:
                result = self.analyze_ab_test(base_model, variant_model)
                stats['results'].append(result)
                stats['tests_analyzed'] += 1

            except Exception as e:
                logger.error(f"Error in A/B test {base_model} vs {variant_model}: {e}")

        logger.info(f"A/B testing complete. Stats: {stats}")
        return stats

    def get_statistics(self) -> Dict:
        """Get A/B testing statistics."""
        return {
            'active_tests': len(self._active_tests),
            'available_methods': ['t_test', 'chi_square']
        }
