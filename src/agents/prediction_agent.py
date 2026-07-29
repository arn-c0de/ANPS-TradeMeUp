"""
Agent 6: Market Prediction Agent - Generate predictions using ML models

OPTIMIZED VERSION:
- ✅ Scoped sessions with context manager (no shared session)
- ✅ Batch transactions (1 commit per batch instead of N)
- ✅ Proper error handling with rollback
- ✅ No session state leaks between batches
"""
import logging
import math
import pickle
import uuid
from datetime import UTC, datetime, timedelta
from pathlib import Path

import numpy as np
import xgboost as xgb
from sqlalchemy.orm import Session

from src.config.settings import settings
from src.ml.feature_engineering import FeatureEngineer
from src.models.analysis import ImpactScore
from src.models.database import get_scoped_session
from src.models.entities import Entity
from src.models.predictions import Prediction
from src.utils.json_helpers import ensure_list

logger = logging.getLogger(__name__)


class PredictionAgent:
    """
    Agent 6: Market Prediction & Ensemble Agent

    Responsibilities:
    - Generate predictions using ML models
    - Calculate direction probabilities
    - Estimate expected returns
    - Store predictions with confidence

    PERFORMANCE OPTIMIZATIONS:
    - Uses scoped sessions for isolation
    - Batch commits (creates all predictions in single transaction)
    - Continues processing even if individual items fail
    """

    # Recorded as model_version when no trained model is on disk, so that
    # heuristic output is never counted as model output.
    HEURISTIC_MODEL_VERSION = "heuristic_v1"

    # Trading days per horizon, used to scale both the expected move and the
    # width of its distribution.
    HORIZON_TRADING_DAYS = {'1d': 1, '5d': 5, '20d': 20}
    DEFAULT_HORIZON_DAYS = 5

    # Label spellings a trained classifier might use for each direction.
    CLASS_LABEL_ALIASES = {
        'down': 'down', '-1': 'down', 'bearish': 'down', '0': 'down',
        'flat': 'flat', 'neutral': 'flat', '1': 'flat',
        'up': 'up', 'bullish': 'up', '2': 'up',
    }

    # Confidence decays with horizon: a 20-day call is a weaker claim than a
    # 1-day one from the same signal. Multiplier applied to the raw score.
    HORIZON_CONFIDENCE_FACTOR = {'1d': 1.0, '5d': 0.92, '20d': 0.80}

    # Daily volatility assumed when sizing the prediction interval, as a
    # decimal fraction. Deliberately a single constant: the feature set
    # carries no per-entity realised volatility yet.
    ASSUMED_DAILY_VOLATILITY = 0.018

    def __init__(self, model_version: str = "xgboost_v1.0"):
        """
        Initialize prediction agent.

        NOTE: No database session parameter!
        Sessions are created per-operation for isolation.

        Args:
            model_version: Model version to use
        """
        self.model_version = model_version

        # Load model (if exists)
        self.model = self._load_model()

        # Define horizons
        self.horizons = ['1d', '5d', '20d']

    def _load_model(self) -> xgb.XGBClassifier | None:
        """
        Load trained model from disk.

        Returns:
            Loaded model or None
        """
        model_path = Path(settings.model_path) / f"{self.model_version}.pkl"

        if model_path.exists():
            try:
                with open(model_path, 'rb') as f:
                    model = pickle.load(f)
                logger.info(f"Loaded model from {model_path}")
                return model
            except Exception as e:
                logger.error(f"Error loading model: {e}")
                return None
        else:
            logger.warning(f"Model not found at {model_path}, predictions will use heuristics")
            return None

    def _horizon_days(self, horizon: str) -> int:
        """Trading days covered by a horizon label."""
        return self.HORIZON_TRADING_DAYS.get(horizon, self.DEFAULT_HORIZON_DAYS)

    def _horizon_return_scale(self, horizon: str) -> float:
        """Scale factor applied to the expected move for a given horizon.

        News impact does not accumulate linearly with time - most of the move
        happens early and then decays. Square-root-of-time is the standard
        first approximation, normalised so the 5-day horizon (the pipeline's
        default) keeps the historical magnitude.
        """
        return math.sqrt(self._horizon_days(horizon) / self.DEFAULT_HORIZON_DAYS)

    def _horizon_adjusted_confidence(self, raw_confidence: float, horizon: str) -> float:
        """Damp confidence for longer horizons and keep it in a sane band."""
        factor = self.HORIZON_CONFIDENCE_FACTOR.get(horizon, 0.92)
        return float(np.clip(raw_confidence * factor, 0.30, 0.95))

    def _build_return_distribution(self, expected_mean: float, horizon: str) -> dict:
        """Build the expected-return payload around ``expected_mean``.

        The quantiles used to be fixed +/-0.01 offsets, which carried no
        distributional information and were identical for every horizon. They
        are now derived from an assumed volatility scaled by sqrt(time), which
        at least widens correctly as the horizon grows.

        `is_percentage` is stated explicitly: values here are decimal
        fractions (0.02 == 2%), and readers previously had to infer that from
        the magnitude.
        """
        sigma = self.ASSUMED_DAILY_VOLATILITY * math.sqrt(self._horizon_days(horizon))

        # Normal quantiles: z(0.05)=-1.645, z(0.25)=-0.674, z(0.75)=+0.674,
        # z(0.95)=+1.645
        return {
            'mean': float(expected_mean),
            'median': float(expected_mean),
            'p05': float(expected_mean - 1.645 * sigma),
            'p25': float(expected_mean - 0.674 * sigma),
            'p75': float(expected_mean + 0.674 * sigma),
            'p95': float(expected_mean + 1.645 * sigma),
            'sigma': float(sigma),
            'is_percentage': False,
        }

    def _map_class_probabilities(self, probas) -> dict:
        """Map a model's probability vector onto up/flat/down.

        Reads the model's own ``classes_`` rather than assuming the column
        order is [down, flat, up]. A model trained with a different label
        order would otherwise have every direction silently inverted.
        """
        direction_probabilities = {'down': 0.0, 'flat': 0.0, 'up': 0.0}

        classes = getattr(self.model, 'classes_', None)
        if classes is not None and len(classes) == len(probas):
            matched = False
            for label, probability in zip(classes, probas):
                key = self.CLASS_LABEL_ALIASES.get(str(label).lower())
                if key:
                    direction_probabilities[key] = float(probability)
                    matched = True
            if matched:
                return direction_probabilities

        # No usable classes_: fall back to the documented order, but say so.
        logger.warning(
            "Model exposes no recognisable classes_ (%r); assuming [down, flat, up]",
            classes,
        )
        order = ['down', 'flat', 'up']
        for key, probability in zip(order, probas):
            direction_probabilities[key] = float(probability)
        return direction_probabilities

    def _predict_with_model(self, features: dict, feature_engineer: FeatureEngineer, horizon: str) -> dict:
        """
        Generate prediction using trained model.

        Args:
            features: Feature dictionary
            feature_engineer: Feature engineer instance
            horizon: Prediction horizon ('1d', '5d', '20d')

        Returns:
            Prediction results
        """
        if self.model is None:
            return self._predict_with_heuristics(features, horizon)

        try:
            # Convert features to array
            feature_names = feature_engineer.get_feature_names()
            X = np.array([[features.get(f, 0.0) for f in feature_names]])

            # Get probabilities
            probas = self.model.predict_proba(X)[0]
            direction_probabilities = self._map_class_probabilities(probas)

            # Expected return, scaled to the horizon (see _horizon_return_scale)
            base_mean = (
                direction_probabilities['up'] * 0.03 +
                direction_probabilities['flat'] * 0.00 +
                direction_probabilities['down'] * -0.02
            )
            expected_mean = base_mean * self._horizon_return_scale(horizon)

            # Feature importance (if available)
            if hasattr(self.model, 'feature_importances_'):
                importances = self.model.feature_importances_
                key_drivers = [
                    {'driver': feature_names[i], 'importance': float(importances[i])}
                    for i in np.argsort(importances)[-5:][::-1]
                ]
            else:
                key_drivers = []

            return {
                'direction_probabilities': direction_probabilities,
                'expected_return': self._build_return_distribution(expected_mean, horizon),
                'confidence': self._horizon_adjusted_confidence(float(max(probas)), horizon),
                'key_drivers': key_drivers,
                'source': 'model',
            }

        except Exception as e:
            logger.error(f"Error in model prediction: {e}")
            return self._predict_with_heuristics(features, horizon)

    def _predict_with_heuristics(self, features: dict, horizon: str) -> dict:
        """
        Generate prediction using simple heuristics (when no model).

        Args:
            features: Feature dictionary
            horizon: Prediction horizon ('1d', '5d', '20d')

        Returns:
            Prediction results
        """
        # Use impact score and sentiment as simple heuristics
        impact = features.get('impact_score', 0.5)
        sentiment = features.get('sentiment_overall', 0.0)

        # Calculate bullish probability based on impact and sentiment
        bullish_prob = 0.33 + (impact * 0.2) + (sentiment * 0.15)
        bullish_prob = np.clip(bullish_prob, 0.1, 0.9)

        bearish_prob = 0.33 - (impact * 0.1) - (sentiment * 0.1)
        bearish_prob = np.clip(bearish_prob, 0.1, 0.5)

        flat_prob = 1.0 - bullish_prob - bearish_prob
        flat_prob = max(0.1, flat_prob)

        # Normalize
        total = bullish_prob + flat_prob + bearish_prob
        direction_probabilities = {
            'up': float(bullish_prob / total),
            'flat': float(flat_prob / total),
            'down': float(bearish_prob / total)
        }

        # Expected return, scaled to the horizon
        expected_mean = (
            direction_probabilities['up'] * (impact * 0.05) +
            direction_probabilities['down'] * -(impact * 0.03)
        ) * self._horizon_return_scale(horizon)

        # Key drivers (heuristic)
        key_drivers = [
            {'driver': 'impact_score', 'importance': 0.40},
            {'driver': 'sentiment_overall', 'importance': 0.30},
            {'driver': 'surprise_factor', 'importance': 0.20},
            {'driver': 'regime_sensitivity', 'importance': 0.10}
        ]

        # Dynamic confidence based on impact and max probability
        # Higher impact and stronger directional signal = higher confidence
        max_prob = max(direction_probabilities.values())
        base_confidence = 0.45 + (impact * 0.25)  # 0.45-0.70 based on impact
        directional_boost = (max_prob - 0.33) * 0.3  # Boost if strong direction
        confidence = np.clip(base_confidence + directional_boost, 0.40, 0.85)

        return {
            'direction_probabilities': direction_probabilities,
            'expected_return': self._build_return_distribution(expected_mean, horizon),
            'confidence': self._horizon_adjusted_confidence(float(confidence), horizon),
            'key_drivers': key_drivers,
            'source': 'heuristic',
        }

    def generate_prediction(
        self,
        entity_id: str,
        news_id: str,
        horizon: str = '5d'
    ) -> Prediction | None:
        """
        Generate a single prediction for an entity based on a news article.
        
        PUBLIC API: Use this for single predictions with auto-commit.
        For batch processing, use process_batch() instead.
        
        Args:
            entity_id: Entity ticker/identifier
            news_id: UUID of news article
            horizon: Prediction horizon ('1d', '5d', '20d')
            
        Returns:
            Prediction object or None if failed
        """
        with get_scoped_session() as db:
            try:
                # Get impact score for this news
                impact = db.query(ImpactScore).filter(
                    ImpactScore.news_id == news_id,
                    ImpactScore.entity_id == entity_id
                ).first()

                if not impact:
                    logger.warning(f"No impact score found for {entity_id}/{news_id}")
                    return None

                # Create feature engineer
                feature_engineer = FeatureEngineer(db)

                # Generate prediction
                prediction = self._generate_prediction_no_commit(
                    db=db,
                    feature_engineer=feature_engineer,
                    entity_id=entity_id,
                    news_id=news_id,
                    horizon=horizon,
                    impact=impact
                )

                if prediction:
                    db.add(prediction)
                    db.commit()
                    logger.info(f"✓ Created prediction for {entity_id} ({horizon})")
                    return prediction
                else:
                    return None

            except Exception as e:
                logger.error(f"Error generating prediction: {e}")
                db.rollback()
                return None

    def process_batch(self, limit: int = 20) -> dict:
        """
        Generate predictions for high-impact news.

        PERFORMANCE: Single transaction for entire batch (30x faster)
        SAFETY: Isolated session with automatic cleanup
        STABILITY: Continues processing even if individual items fail

        Args:
            limit: Maximum number of impact scores to process

        Returns:
            Statistics dictionary
        """
        # Use scoped session for isolation
        with get_scoped_session() as db:
            # Create feature engineer with this session
            feature_engineer = FeatureEngineer(db)

            # Find high-impact scores without predictions
            impact_scores = self._find_impact_without_predictions(db, limit)

            if not impact_scores:
                logger.info("No impact scores to process for predictions")
                return {
                    'processed': 0,
                    'predictions_created': 0,
                    'skipped_low_confidence': 0,
                    'errors': 0
                }

            logger.info(f"Generating predictions for {len(impact_scores)} impact scores")

            stats = {
                'processed': 0,
                'predictions_created': 0,
                'skipped_low_confidence': 0,
                'errors': 0
            }

            all_predictions = []

            # Horizon coverage for the selected impacts, in one query.
            covered = self._existing_horizons_by_news(
                db, {impact.entity_id for impact in impact_scores}
            )

            # Process all impact scores WITHOUT committing
            for impact in impact_scores:
                try:
                    # Reuse the coverage map built during selection instead of
                    # reloading every prediction for this entity a second time.
                    existing_horizons = covered.get(
                        (impact.entity_id, str(impact.news_id)), set()
                    )

                    # Generate predictions for missing horizons
                    for horizon in self.horizons:
                        if horizon in existing_horizons:
                            continue  # Skip if already exists

                        # Generate prediction (without commit)
                        prediction = self._generate_prediction_no_commit(
                            db,
                            feature_engineer,
                            entity_id=impact.entity_id,
                            news_id=str(impact.news_id),
                            horizon=horizon,
                            impact=impact
                        )

                        if prediction:
                            all_predictions.append(prediction)
                            stats['predictions_created'] += 1

                    stats['processed'] += 1

                except Exception as e:
                    # Log error but CONTINUE processing other items
                    logger.error(f"Error processing impact {impact.score_id}: {e}")
                    stats['errors'] += 1
                    continue

            # ✅ CRITICAL: Bulk save all predictions
            if all_predictions:
                db.bulk_save_objects(all_predictions)
                logger.info(f"Bulk saved {len(all_predictions)} predictions")

            # ✅ SINGLE COMMIT for entire batch
            # (Happens automatically in context manager on success)

            logger.info(f"Prediction generation complete. Stats: {stats}")
            return stats

    def _find_impact_without_predictions(
        self,
        db: Session,
        limit: int
    ) -> list[ImpactScore]:
        """
        Find high-impact scores without predictions.

        Args:
            db: Database session
            limit: Maximum number to return

        Returns:
            List of ImpactScore objects
        """
        # Get high-impact scores that are recent (last 7 days)
        # Use UTC to match impact score timestamps
        cutoff_date = datetime.now(UTC) - timedelta(days=7)

        # Use configurable threshold (default 0.4, can be lowered to 0.3 for more predictions)
        min_impact_threshold = settings.min_prediction_impact_threshold

        impact_scores = db.query(ImpactScore).filter(
            ImpactScore.impact_score >= min_impact_threshold,  # Only significant impact
            ImpactScore.created_at >= cutoff_date  # Recent only
        ).order_by(
            ImpactScore.created_at.desc()  # Newest first
        ).limit(limit * 5).all()  # Get more candidates for filtering

        if not impact_scores:
            logger.info(f"No high-impact scores found (impact >= {min_impact_threshold})")
            return []

        logger.info(f"Found {len(impact_scores)} high-impact scores to check")

        # Build the coverage map once for every candidate entity. This used to
        # be a query per candidate per horizon - roughly 300 round trips, each
        # loading every prediction the entity ever had.
        covered = self._existing_horizons_by_news(
            db, {impact.entity_id for impact in impact_scores}
        )

        # Filter out those that already have predictions for ALL horizons
        to_predict = []
        all_horizons = set(self.horizons)

        for impact in impact_scores:
            key = (impact.entity_id, str(impact.news_id))
            missing_horizons = all_horizons - covered.get(key, set())
            if missing_horizons:
                logger.debug(f"Entity {impact.entity_id} missing predictions for {missing_horizons}")
                to_predict.append(impact)
                if len(to_predict) >= limit:
                    break

        logger.info(f"Found {len(to_predict)} impact scores needing predictions")
        return to_predict

    def _existing_horizons_by_news(self, db: Session, entity_ids: set) -> dict:
        """Map (entity_id, news_id) -> set of horizons already predicted.

        related_news_ids is a JSON array, so membership is resolved in Python -
        but over a single query for all entities rather than one per entity and
        horizon.
        """
        if not entity_ids:
            return {}

        rows = db.query(
            Prediction.entity_id,
            Prediction.horizon,
            Prediction.related_news_ids,
        ).filter(Prediction.entity_id.in_(entity_ids)).all()

        covered: dict[tuple, set] = {}
        for entity_id, horizon, related_news_ids in rows:
            for news_id in ensure_list(related_news_ids, []):
                covered.setdefault((entity_id, str(news_id)), set()).add(horizon)
        return covered

    def _generate_prediction_no_commit(
        self,
        db: Session,
        feature_engineer: FeatureEngineer,
        entity_id: str,
        news_id: str,
        horizon: str,
        impact: ImpactScore
    ) -> Prediction | None:
        """
        Generate prediction for entity WITHOUT committing.

        This allows batching multiple predictions into a single transaction.

        Args:
            db: Database session
            feature_engineer: Feature engineer instance
            entity_id: Entity ticker
            news_id: News article ID
            horizon: Prediction horizon (1d, 5d, 20d)
            impact: ImpactScore object

        Returns:
            Prediction object (not yet committed) or None
        """
        try:
            # Check if entity exists
            entity = db.query(Entity).filter(Entity.entity_id == entity_id).first()
            if not entity:
                logger.warning(f"Entity {entity_id} not found")
                return None

            # Only predict if impact score is significant
            # Use configurable threshold (default 0.4, can be lowered to 0.3 for more predictions)
            min_impact_threshold = settings.min_prediction_impact_threshold
            if impact.impact_score < min_impact_threshold:
                logger.debug(f"Impact score too low ({impact.impact_score:.2f} < {min_impact_threshold}), skipping prediction")
                return None

            # Extract features
            features = feature_engineer.extract_features_for_prediction(
                entity_id=entity_id,
                news_id=news_id,
                as_of_date=impact.created_at
            )

            # Generate prediction
            result = self._predict_with_model(features, feature_engineer, horizon)

            # Record which path actually produced this. Labelling a heuristic
            # as the XGBoost model made the performance monitor and the A/B
            # tests compare something that never ran.
            source = result.get('source', 'heuristic')
            if source == 'model':
                model_version = self.model_version
                model_contributions = {self.model_version: 1.0}
            else:
                model_version = self.HEURISTIC_MODEL_VERSION
                model_contributions = {self.HEURISTIC_MODEL_VERSION: 1.0}

            # Create prediction record
            prediction = Prediction(
                prediction_id=uuid.uuid4(),
                entity_id=entity_id,
                timestamp=impact.created_at,
                horizon=horizon,
                direction_probabilities=result['direction_probabilities'],
                expected_return=result['expected_return'],
                confidence=result['confidence'],
                model_contributions=model_contributions,
                key_drivers=result['key_drivers'],
                model_version=model_version,
                related_news_ids=[news_id],
                created_at=datetime.now(UTC)
            )

            logger.debug(
                f"Generated prediction for {entity_id} ({horizon}): "
                f"up={result['direction_probabilities']['up']:.2f}, "
                f"expected_return={result['expected_return']['mean']:.3f}"
            )

            return prediction

        except Exception as e:
            logger.error(f"Error generating prediction for {entity_id}/{news_id}: {e}", exc_info=True)
            return None

    def get_statistics(self) -> dict:
        """
        Get prediction statistics.

        Uses scoped session for isolation.
        """
        from sqlalchemy import func

        with get_scoped_session() as db:
            total_predictions = db.query(Prediction).count()

            # Count by horizon
            by_horizon = db.query(
                Prediction.horizon,
                func.count(Prediction.prediction_id).label('count'),
                func.avg(Prediction.confidence).label('avg_confidence')
            ).group_by(Prediction.horizon).all()

            # High confidence predictions (>= 0.7)
            high_confidence = db.query(Prediction).filter(
                Prediction.confidence >= 0.7
            ).count()

            return {
                'total_predictions': total_predictions,
                'high_confidence_count': high_confidence,
                'by_horizon': {
                    horizon: {'count': count, 'avg_confidence': float(avg_conf)}
                    for horizon, count, avg_conf in by_horizon
                }
            }
