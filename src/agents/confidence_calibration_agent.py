"""Agent 6.5: Confidence Calibration Agent - Calibrate prediction confidence scores."""
import logging
from datetime import UTC, datetime, timedelta

import numpy as np

from src.models.database import SessionLocal
from src.models.predictions import Prediction, PredictionOutcome
from src.utils.prediction_math import direction_was_correct

logger = logging.getLogger(__name__)

# Upper edges of the confidence buckets used for the reliability diagram. The
# first bucket starts at 0.0 and each subsequent one starts where the previous
# ended, so the set covers [0.0, 1.0] with no gaps.
CONFIDENCE_BIN_EDGES = (0.5, 0.6, 0.7, 0.8, 0.9, 1.0)

# Below this many scored predictions the reliability diagram is noise.
MIN_PREDICTIONS_FOR_CALIBRATION = 10


def _confidence_bins() -> list[tuple[float, float]]:
    """Return the (low, high) confidence buckets, lowest first."""
    edges = (0.0,) + CONFIDENCE_BIN_EDGES
    return [(edges[i], edges[i + 1]) for i in range(len(edges) - 1)]


def _find_bin_index(confidence: float) -> int | None:
    """Return the bucket a confidence falls into, or None if out of range.

    The top bucket is closed on both ends so a confidence of exactly 1.0 is
    scored rather than silently dropped.
    """
    bins = _confidence_bins()
    for index, (low, high) in enumerate(bins):
        is_last = index == len(bins) - 1
        if low <= confidence < high or (is_last and confidence == high):
            return index
    return None


class ConfidenceCalibrationAgent:
    """
    Agent 6.5: Confidence Calibration Agent

    Responsibilities:
    - Calibrate confidence scores based on historical accuracy
    - Identify overconfident/underconfident predictions
    - Adjust model confidence dynamically
    - Track calibration metrics

    Note: Uses scoped sessions internally for better isolation, so it takes no
    database session.
    """

    def calculate_calibration_error(self, lookback_days: int = 30) -> dict:
        """
        Calculate expected calibration error (ECE).

        Args:
            lookback_days: Historical period to analyze

        Returns:
            Calibration metrics
        """
        try:
            with SessionLocal() as db:
                scored = self._score_recent_predictions(db, lookback_days)
        except Exception as e:
            logger.error(f"Error calculating calibration error: {e}")
            return {'error': str(e)}

        if scored is None:
            return {'error': 'insufficient_data'}

        return self._summarize_calibration(scored)

    def _score_recent_predictions(
        self, db, lookback_days: int
    ) -> list[tuple[int, float, bool]] | None:
        """Return (bin_index, confidence, was_correct) per resolved prediction.

        Returns None when there is too little history to calibrate against.
        """
        cutoff = datetime.now(UTC) - timedelta(days=lookback_days)

        predictions = db.query(Prediction).join(
            PredictionOutcome,
            Prediction.prediction_id == PredictionOutcome.prediction_id
        ).filter(
            Prediction.created_at >= cutoff
        ).all()

        if len(predictions) < MIN_PREDICTIONS_FOR_CALIBRATION:
            logger.warning("Insufficient predictions for calibration")
            return None

        # Fetch every outcome up front. Querying inside the loop added one
        # round trip per prediction on top of the join that already
        # selected them.
        outcomes = {
            row.prediction_id: row
            for row in db.query(PredictionOutcome).filter(
                PredictionOutcome.prediction_id.in_(
                    [pred.prediction_id for pred in predictions]
                )
            ).all()
        }

        scored = []
        for pred in predictions:
            outcome = outcomes.get(pred.prediction_id)
            if not outcome:
                continue

            bin_index = _find_bin_index(pred.confidence)
            if bin_index is None:
                continue

            scored.append(
                (bin_index, pred.confidence, direction_was_correct(pred, outcome.actual_return))
            )

        return scored

    @staticmethod
    def _summarize_calibration(scored: list[tuple[int, float, bool]]) -> dict:
        """Turn per-prediction scores into a reliability diagram plus ECE."""
        bins = _confidence_bins()
        total_samples = len(scored)

        ece = 0.0
        by_bin = []

        for index, (low, high) in enumerate(bins):
            confidences = [conf for bin_index, conf, _ in scored if bin_index == index]
            if not confidences:
                continue

            correct = [hit for bin_index, _, hit in scored if bin_index == index]
            avg_confidence = float(np.mean(confidences))
            avg_accuracy = float(np.mean(correct))
            bin_error = abs(avg_confidence - avg_accuracy)

            ece += (len(confidences) / total_samples) * bin_error

            by_bin.append({
                'bin': f"{low:.1f}-{high:.1f}",
                'bin_min': low,
                'bin_max': high,
                'avg_confidence': avg_confidence,
                'avg_accuracy': avg_accuracy,
                'sample_count': len(confidences),
                'calibration_error': bin_error,
            })

        return {
            'expected_calibration_error': ece,
            'total_predictions': total_samples,
            'by_bin': by_bin,
        }

    def calibrate_confidence(
        self,
        raw_confidence: float,
        model_id: str = 'default',
        calibration: dict | None = None,
    ) -> float:
        """
        Calibrate a raw confidence score.

        Args:
            raw_confidence: Uncalibrated confidence
            model_id: Model identifier
            calibration: Pre-computed output of :meth:`calculate_calibration_error`.
                Pass it when calibrating many predictions - recomputing it per
                prediction re-scans 90 days of history every single time.

        Returns:
            Calibrated confidence
        """
        if calibration is None:
            calibration = self.calculate_calibration_error(lookback_days=90)

        if 'error' in calibration:
            # No calibration available, return raw
            return raw_confidence

        bin_index = _find_bin_index(raw_confidence)
        if bin_index is None:
            return raw_confidence

        low, high = _confidence_bins()[bin_index]
        for bin_data in calibration.get('by_bin', []):
            if bin_data['bin_min'] == low and bin_data['bin_max'] == high:
                # Use historical accuracy as calibrated confidence
                return bin_data['avg_accuracy']

        # No history in this bucket, so there is nothing to correct towards.
        return raw_confidence

    def process_batch(self, limit: int = 100) -> dict:
        """
        Recalibrate recent predictions.

        Args:
            limit: Number of predictions to recalibrate

        Returns:
            Statistics
        """
        stats = {
            'processed': 0,
            'avg_raw_confidence': 0.0,
            'avg_calibrated_confidence': 0.0,
            'errors': 0
        }

        try:
            with SessionLocal() as db:
                predictions = db.query(Prediction).order_by(
                    Prediction.created_at.desc()
                ).limit(limit).all()

                logger.info(f"Recalibrating {len(predictions)} predictions")

                # Computed once for the whole batch. Calling calibrate_confidence
                # without it re-ran a 90-day scan (plus its own per-row lookups)
                # for every prediction in the batch.
                calibration = self.calculate_calibration_error(lookback_days=90)

                raw_confidences = []
                calibrated_confidences = []

                for pred in predictions:
                    try:
                        calibrated_conf = self.calibrate_confidence(
                            pred.confidence, pred.model_version, calibration=calibration
                        )

                        raw_confidences.append(pred.confidence)
                        calibrated_confidences.append(calibrated_conf)

                        pred.calibrated_confidence = calibrated_conf
                        stats['processed'] += 1
                    except Exception as e:
                        stats['errors'] += 1
                        logger.error(f"Error calibrating prediction {pred.prediction_id}: {e}")

                db.commit()

                if raw_confidences:
                    stats['avg_raw_confidence'] = float(np.mean(raw_confidences))
                    stats['avg_calibrated_confidence'] = float(np.mean(calibrated_confidences))

            logger.info(f"Confidence calibration complete. Stats: {stats}")
            return stats
        except Exception as e:
            logger.error(f"Error in process_batch: {e}")
            return {'processed': 0, 'errors': 1, 'error': str(e)}

    def get_statistics(self) -> dict:
        """Get calibration statistics."""
        return self.calculate_calibration_error(lookback_days=90)
