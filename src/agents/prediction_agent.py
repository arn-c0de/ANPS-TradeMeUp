"""Agent 6: Market Prediction Agent - Generate predictions using ML models."""
import logging
from typing import Dict, List, Optional
from datetime import datetime
import uuid
from pathlib import Path
import pickle
import numpy as np
from sqlalchemy.orm import Session
import xgboost as xgb

from src.models.entities import Entity
from src.models.analysis import ImpactScore
from src.models.predictions import Prediction
from src.ml.feature_engineering import FeatureEngineer
from src.config.settings import settings

logger = logging.getLogger(__name__)


class PredictionAgent:
    """
    Agent 6: Market Prediction & Ensemble Agent

    Responsibilities:
    - Generate predictions using ML models
    - Calculate direction probabilities
    - Estimate expected returns
    - Store predictions with confidence
    """

    def __init__(self, db: Session, model_version: str = "xgboost_v1.0"):
        """
        Initialize prediction agent.

        Args:
            db: Database session
            model_version: Model version to use
        """
        self.db = db
        self.model_version = model_version
        self.feature_engineer = FeatureEngineer(db)

        # Load model (if exists)
        self.model = self._load_model()

        # Define horizons
        self.horizons = ['1d', '5d', '20d']

    def _load_model(self) -> Optional[xgb.XGBClassifier]:
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

    def _predict_with_model(self, features: Dict) -> Dict:
        """
        Generate prediction using trained model.

        Args:
            features: Feature dictionary

        Returns:
            Prediction results
        """
        if self.model is None:
            return self._predict_with_heuristics(features)

        try:
            # Convert features to array
            feature_names = self.feature_engineer.get_feature_names()
            X = np.array([[features.get(f, 0.0) for f in feature_names]])

            # Get probabilities
            probas = self.model.predict_proba(X)[0]

            # Map to up/flat/down
            # Assuming classes: [down, flat, up]
            direction_probabilities = {
                'down': float(probas[0]) if len(probas) > 0 else 0.33,
                'flat': float(probas[1]) if len(probas) > 1 else 0.34,
                'up': float(probas[2]) if len(probas) > 2 else 0.33
            }

            # Calculate expected return
            # Simplified: Use probabilities and typical returns
            expected_mean = (
                direction_probabilities['up'] * 0.03 +
                direction_probabilities['flat'] * 0.00 +
                direction_probabilities['down'] * -0.02
            )

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
                'expected_return': {
                    'mean': expected_mean,
                    'median': expected_mean,
                    'p25': expected_mean - 0.01,
                    'p75': expected_mean + 0.01,
                    'p95': expected_mean + 0.03
                },
                'confidence': max(probas),
                'key_drivers': key_drivers
            }

        except Exception as e:
            logger.error(f"Error in model prediction: {e}")
            return self._predict_with_heuristics(features)

    def _predict_with_heuristics(self, features: Dict) -> Dict:
        """
        Generate prediction using simple heuristics (when no model).

        Args:
            features: Feature dictionary

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

        # Expected return
        expected_mean = (
            direction_probabilities['up'] * (impact * 0.05) +
            direction_probabilities['down'] * -(impact * 0.03)
        )

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
            'expected_return': {
                'mean': expected_mean,
                'median': expected_mean,
                'p25': expected_mean - 0.015,
                'p75': expected_mean + 0.015,
                'p95': expected_mean + 0.04
            },
            'confidence': float(confidence),
            'key_drivers': key_drivers
        }

    def generate_prediction(
        self,
        entity_id: str,
        news_id: str,
        horizon: str = '5d'
    ) -> Optional[Prediction]:
        """
        Generate prediction for entity based on news.

        Args:
            entity_id: Entity ticker
            news_id: News article ID
            horizon: Prediction horizon (1d, 5d, 20d)

        Returns:
            Prediction object or None
        """
        try:
            # Check if entity exists
            entity = self.db.query(Entity).filter(Entity.entity_id == entity_id).first()
            if not entity:
                logger.warning(f"Entity {entity_id} not found")
                return None

            # Check if impact score exists (indicates processed article)
            impact = self.db.query(ImpactScore).filter(
                ImpactScore.news_id == news_id,
                ImpactScore.entity_id == entity_id
            ).first()

            if not impact:
                logger.warning(f"No impact score for {news_id} / {entity_id}")
                return None

            # Only predict if impact score is significant
            if impact.impact_score < 0.4:
                logger.debug(f"Impact score too low ({impact.impact_score:.2f}), skipping prediction")
                return None

            # Extract features
            features = self.feature_engineer.extract_features_for_prediction(
                entity_id=entity_id,
                news_id=news_id,
                as_of_date=impact.created_at
            )

            # Generate prediction
            result = self._predict_with_model(features)

            # Create prediction record
            prediction = Prediction(
                prediction_id=uuid.uuid4(),
                entity_id=entity_id,
                timestamp=impact.created_at,
                horizon=horizon,
                direction_probabilities=result['direction_probabilities'],
                expected_return=result['expected_return'],
                confidence=result['confidence'],
                model_contributions={'xgboost': 1.0},  # Single model for MVP
                key_drivers=result['key_drivers'],
                model_version=self.model_version,
                related_news_ids=[str(news_id)],
                created_at=datetime.utcnow()
            )

            # Save to database
            self.db.add(prediction)
            self.db.commit()
            self.db.refresh(prediction)

            logger.info(
                f"Generated prediction for {entity_id}: "
                f"up={result['direction_probabilities']['up']:.2f}, "
                f"expected_return={result['expected_return']['mean']:.3f}"
            )

            return prediction

        except Exception as e:
            self.db.rollback()
            logger.error(f"Error generating prediction: {e}")
            return None

    def process_batch(self, limit: int = 10) -> Dict:
        """
        Generate predictions for high-impact news.

        Args:
            limit: Maximum number of predictions to generate

        Returns:
            Statistics dictionary
        """
        # Find high-impact scores without predictions
        # Note: For SQLite, we can't do array containment queries efficiently
        # So we'll just find impact scores and check if predictions exist separately
        
        impact_scores = self.db.query(ImpactScore).filter(
            ImpactScore.impact_score >= 0.4  # Only significant impact
        ).order_by(
            ImpactScore.impact_score.desc()
        ).limit(limit * 2).all()  # Get more candidates
        
        # Filter out those that already have predictions
        to_predict = []
        for impact in impact_scores:
            # Check if prediction exists for this impact score
            existing = self.db.query(Prediction).filter(
                Prediction.entity_id == impact.entity_id,
                Prediction.related_news_ids.like(f'%{impact.news_id}%')  # Simple JSON search
            ).first()
            
            if not existing:
                to_predict.append(impact)
                if len(to_predict) >= limit:
                    break
        
        impact_scores = to_predict

        logger.info(f"Generating predictions for {len(impact_scores)} impact scores")

        stats = {
            'processed': 0,
            'predictions_created': 0,
            'skipped_low_confidence': 0,
            'errors': 0
        }

        for impact in impact_scores:
            try:
                prediction = self.generate_prediction(
                    entity_id=impact.entity_id,
                    news_id=str(impact.news_id),
                    horizon='5d'
                )

                stats['processed'] += 1

                if prediction:
                    stats['predictions_created'] += 1
                else:
                    stats['skipped_low_confidence'] += 1

            except Exception as e:
                stats['errors'] += 1
                logger.error(f"Error processing impact score: {e}")
                continue

        logger.info(f"Prediction generation complete. Stats: {stats}")
        return stats

    def get_statistics(self) -> Dict:
        """Get prediction statistics."""
        from sqlalchemy import func

        total_predictions = self.db.query(Prediction).count()

        # Average confidence
        avg_confidence = self.db.query(
            func.avg(Prediction.confidence)
        ).scalar()

        # Distribution of predictions
        bullish = self.db.query(Prediction).filter(
            func.json_extract(Prediction.direction_probabilities, '$.up') > 0.5
        ).count()

        bearish = self.db.query(Prediction).filter(
            func.json_extract(Prediction.direction_probabilities, '$.down') > 0.5
        ).count()

        return {
            'total_predictions': total_predictions,
            'average_confidence': float(avg_confidence) if avg_confidence else 0.0,
            'bullish_predictions': bullish,
            'bearish_predictions': bearish,
            'neutral_predictions': total_predictions - bullish - bearish
        }
