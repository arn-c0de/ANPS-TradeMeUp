"""Agent 6.5: Confidence Calibration Agent - Calibrate prediction confidence scores."""
import logging
from typing import Dict, List
from datetime import datetime, timedelta
from sqlalchemy.orm import Session
from sqlalchemy import func
import numpy as np

from src.models.predictions import Prediction, PredictionOutcome

logger = logging.getLogger(__name__)


class ConfidenceCalibrationAgent:
    """
    Agent 6.5: Confidence Calibration Agent

    Responsibilities:
    - Calibrate confidence scores based on historical accuracy
    - Identify overconfident/underconfident predictions
    - Adjust model confidence dynamically
    - Track calibration metrics
    """

    def __init__(self, db: Session):
        """Initialize confidence calibration agent."""
        self.db = db

    def calculate_calibration_error(self, lookback_days: int = 30) -> Dict:
        """
        Calculate expected calibration error (ECE).

        Args:
            lookback_days: Historical period to analyze

        Returns:
            Calibration metrics
        """
        cutoff = datetime.utcnow() - timedelta(days=lookback_days)

        # Fetch predictions with outcomes
        predictions = self.db.query(Prediction).join(
            PredictionOutcome,
            Prediction.prediction_id == PredictionOutcome.prediction_id
        ).filter(
            Prediction.created_at >= cutoff
        ).all()

        if len(predictions) < 10:
            logger.warning("Insufficient predictions for calibration")
            return {'error': 'insufficient_data'}

        # Bin predictions by confidence
        bins = [0.0, 0.5, 0.6, 0.7, 0.8, 0.9, 1.0]
        bin_counts = {i: [] for i in range(len(bins) - 1)}
        bin_accuracies = {i: [] for i in range(len(bins) - 1)}

        for pred in predictions:
            confidence = pred.confidence
            outcome = self.db.query(PredictionOutcome).filter(
                PredictionOutcome.prediction_id == pred.prediction_id
            ).first()

            if not outcome:
                continue

            # Determine if prediction was correct
            was_correct = self._check_prediction_accuracy(pred, outcome)

            # Find bin
            for i in range(len(bins) - 1):
                if bins[i] <= confidence < bins[i + 1]:
                    bin_counts[i].append(confidence)
                    bin_accuracies[i].append(1 if was_correct else 0)
                    break

        # Calculate ECE
        total_samples = sum(len(v) for v in bin_counts.values())
        ece = 0.0

        calibration_data = []

        for i in range(len(bins) - 1):
            if len(bin_counts[i]) > 0:
                avg_confidence = np.mean(bin_counts[i])
                avg_accuracy = np.mean(bin_accuracies[i])
                bin_weight = len(bin_counts[i]) / total_samples

                ece += bin_weight * abs(avg_confidence - avg_accuracy)

                calibration_data.append({
                    'bin': f"{bins[i]:.1f}-{bins[i+1]:.1f}",
                    'avg_confidence': float(avg_confidence),
                    'avg_accuracy': float(avg_accuracy),
                    'sample_count': len(bin_counts[i]),
                    'calibration_error': float(abs(avg_confidence - avg_accuracy))
                })

        return {
            'expected_calibration_error': float(ece),
            'total_predictions': total_samples,
            'by_bin': calibration_data
        }

    def _check_prediction_accuracy(self, prediction: Prediction, outcome: PredictionOutcome) -> bool:
        """Check if prediction was accurate."""
        # Simple direction check
        predicted_direction = prediction.predicted_direction
        actual_return = outcome.actual_return

        if predicted_direction == 'up':
            return actual_return > 0
        elif predicted_direction == 'down':
            return actual_return < 0
        else:  # flat
            return abs(actual_return) < 0.01

    def calibrate_confidence(self, raw_confidence: float, model_id: str = 'default') -> float:
        """
        Calibrate a raw confidence score.

        Args:
            raw_confidence: Uncalibrated confidence
            model_id: Model identifier

        Returns:
            Calibrated confidence
        """
        # Get historical calibration data
        calibration = self.calculate_calibration_error(lookback_days=90)

        if 'error' in calibration:
            # No calibration available, return raw
            return raw_confidence

        # Find matching bin
        by_bin = calibration.get('by_bin', [])

        for bin_data in by_bin:
            bin_range = bin_data['bin'].split('-')
            bin_min = float(bin_range[0])
            bin_max = float(bin_range[1])

            if bin_min <= raw_confidence < bin_max:
                # Use historical accuracy as calibrated confidence
                return bin_data['avg_accuracy']

        # Fallback: return raw confidence
        return raw_confidence

    def process_batch(self, limit: int = 100) -> Dict:
        """
        Recalibrate recent predictions.

        Args:
            limit: Number of predictions to recalibrate

        Returns:
            Statistics
        """
        # Get recent predictions
        predictions = self.db.query(Prediction).order_by(
            Prediction.created_at.desc()
        ).limit(limit).all()

        logger.info(f"Recalibrating {len(predictions)} predictions")

        stats = {
            'processed': 0,
            'avg_raw_confidence': 0.0,
            'avg_calibrated_confidence': 0.0,
            'errors': 0
        }

        raw_confidences = []
        calibrated_confidences = []

        for pred in predictions:
            try:
                raw_conf = pred.confidence
                calibrated_conf = self.calibrate_confidence(raw_conf, pred.model_id)

                raw_confidences.append(raw_conf)
                calibrated_confidences.append(calibrated_conf)

                # Update prediction with calibrated confidence
                pred.calibrated_confidence = calibrated_conf
                stats['processed'] += 1

            except Exception as e:
                stats['errors'] += 1
                logger.error(f"Error calibrating prediction {pred.prediction_id}: {e}")

        self.db.commit()

        if raw_confidences:
            stats['avg_raw_confidence'] = float(np.mean(raw_confidences))
            stats['avg_calibrated_confidence'] = float(np.mean(calibrated_confidences))

        logger.info(f"Confidence calibration complete. Stats: {stats}")
        return stats

    def get_statistics(self) -> Dict:
        """Get calibration statistics."""
        return self.calculate_calibration_error(lookback_days=90)
