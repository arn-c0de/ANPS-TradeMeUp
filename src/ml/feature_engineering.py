"""Feature engineering for prediction models."""
import logging
from datetime import datetime

import numpy as np
import pandas as pd
from sqlalchemy.orm import Session

from src.models.analysis import ImpactScore, MarketRegime, SurpriseScore
from src.models.predictions import MarketData
from src.models.processed_news import ProcessedNews

logger = logging.getLogger(__name__)


class FeatureEngineer:
    """Feature engineering for ML models."""

    # Cap on rows pulled into a training dataset (MVP limit).
    MAX_TRAINING_SAMPLES = 100

    def __init__(self, db: Session):
        """
        Initialize feature engineer.

        Args:
            db: Database session
        """
        self.db = db

    def extract_features_for_prediction(
        self,
        entity_id: str,
        news_id: str,
        as_of_date: datetime
    ) -> dict:
        """
        Extract features for a single prediction.

        Args:
            entity_id: Entity ticker
            news_id: News article ID
            as_of_date: Date to extract features

        Returns:
            Feature dictionary
        """
        features = {}

        try:
            # 1. Impact score features
            impact = self.db.query(ImpactScore).filter(
                ImpactScore.news_id == news_id,
                ImpactScore.entity_id == entity_id
            ).first()

            if impact:
                features['impact_score'] = impact.impact_score
                features['impact_confidence'] = impact.confidence
                features['expected_volatility'] = impact.expected_volatility_impact

                # Impact breakdown
                breakdown = impact.impact_breakdown or {}
                features['news_importance'] = breakdown.get('news_importance', 0.5)
                features['regime_sensitivity'] = breakdown.get('regime_sensitivity', 1.0)
                features['sector_sensitivity'] = breakdown.get('sector_sensitivity', 1.0)
                features['surprise_factor'] = breakdown.get('surprise_factor', 1.0)
            else:
                # Default values if no impact score
                features['impact_score'] = 0.5
                features['impact_confidence'] = 0.5
                features['expected_volatility'] = 0.0
                features['news_importance'] = 0.5
                features['regime_sensitivity'] = 1.0
                features['sector_sensitivity'] = 1.0
                features['surprise_factor'] = 1.0

            # 2. Sentiment features
            processed = self.db.query(ProcessedNews).filter(
                ProcessedNews.news_id == news_id
            ).first()

            if processed and processed.sentiment:
                features['sentiment_overall'] = processed.sentiment.get('overall', 0.0)
                features['sentiment_confidence'] = processed.sentiment.get('confidence', 0.5)
            else:
                features['sentiment_overall'] = 0.0
                features['sentiment_confidence'] = 0.5

            # Event type (one-hot encoding)
            if processed:
                event_type = processed.event_type or 'other'
                features['event_earnings'] = 1 if event_type == 'earnings' else 0
                features['event_ma'] = 1 if event_type == 'm_and_a' else 0
                features['event_regulation'] = 1 if event_type == 'regulation' else 0
                features['event_macro'] = 1 if event_type == 'macro' else 0
            else:
                features['event_earnings'] = 0
                features['event_ma'] = 0
                features['event_regulation'] = 0
                features['event_macro'] = 0

            # 3. Surprise features
            surprise = self.db.query(SurpriseScore).filter(
                SurpriseScore.news_id == news_id
            ).first()

            if surprise and surprise.surprise_normalized is not None:
                features['has_surprise'] = 1
                features['surprise_magnitude'] = abs(surprise.surprise_normalized)
                features['surprise_direction'] = 1 if surprise.surprise_normalized > 0 else -1
            else:
                features['has_surprise'] = 0
                features['surprise_magnitude'] = 0.0
                features['surprise_direction'] = 0

            # 4. Regime features
            regime = self.db.query(MarketRegime).filter(
                MarketRegime.timestamp <= as_of_date
            ).order_by(MarketRegime.timestamp.desc()).first()

            if regime:
                reg_data = regime.regime or {}
                features['regime_volatility_high'] = 1 if reg_data.get('volatility') == 'high' else 0
                features['regime_trend_bear'] = 1 if reg_data.get('trend') == 'bear' else 0
                features['regime_risk_off'] = 1 if reg_data.get('risk_appetite') == 'risk_off' else 0

                # VIX level
                metadata = regime.regime_metadata or {}
                features['vix_level'] = metadata.get('vix_level', 20.0)
            else:
                features['regime_volatility_high'] = 0
                features['regime_trend_bear'] = 0
                features['regime_risk_off'] = 0
                features['vix_level'] = 20.0

            # 5. Technical features (if market data available)
            # For MVP, use simple heuristics
            features['hour_of_day'] = as_of_date.hour
            features['day_of_week'] = as_of_date.weekday()

            return features

        except Exception as e:
            logger.error(f"Error extracting features: {e}")
            # Return default features
            return self._get_default_features()

    def _get_default_features(self) -> dict:
        """Get default feature values."""
        return {
            'impact_score': 0.5,
            'impact_confidence': 0.5,
            'expected_volatility': 0.0,
            'news_importance': 0.5,
            'regime_sensitivity': 1.0,
            'sector_sensitivity': 1.0,
            'surprise_factor': 1.0,
            'sentiment_overall': 0.0,
            'sentiment_confidence': 0.5,
            'event_earnings': 0,
            'event_ma': 0,
            'event_regulation': 0,
            'event_macro': 0,
            'has_surprise': 0,
            'surprise_magnitude': 0.0,
            'surprise_direction': 0,
            'regime_volatility_high': 0,
            'regime_trend_bear': 0,
            'regime_risk_off': 0,
            'vix_level': 20.0,
            'hour_of_day': 12,
            'day_of_week': 2
        }

    def create_training_dataset(
        self,
        start_date: datetime,
        end_date: datetime,
        horizon_days: int = 5
    ) -> pd.DataFrame:
        """
        Create training dataset with features and targets.

        Args:
            start_date: Start date for dataset
            end_date: End date for dataset
            horizon_days: Forward return horizon

        Returns:
            DataFrame with features and targets
        """
        logger.warning(
            "create_training_dataset produces SYNTHETIC targets: target_return is "
            "random noise, not a realised forward return. A model trained on this "
            "dataset learns nothing. Implement the forward-return lookup before "
            "using it for anything but plumbing tests."
        )
        logger.info(f"Creating training dataset from {start_date} to {end_date}")

        # This is a simplified version - in production would be more complex
        data = []

        # Get all impact scores in date range
        impact_scores = self.db.query(ImpactScore).filter(
            ImpactScore.created_at >= start_date,
            ImpactScore.created_at <= end_date
        ).all()

        logger.info(f"Found {len(impact_scores)} impact scores to process")

        if len(impact_scores) > self.MAX_TRAINING_SAMPLES:
            logger.warning(
                "Truncating to the first %d of %d impact scores (MVP limit)",
                self.MAX_TRAINING_SAMPLES,
                len(impact_scores),
            )

        for impact in impact_scores[:self.MAX_TRAINING_SAMPLES]:
            try:
                # Extract features
                features = self.extract_features_for_prediction(
                    entity_id=impact.entity_id,
                    news_id=str(impact.news_id),
                    as_of_date=impact.created_at
                )

                # Add identifiers
                features['news_id'] = str(impact.news_id)
                features['entity_id'] = impact.entity_id
                features['timestamp'] = impact.created_at

                # TODO: Calculate the realised forward return over horizon_days
                # from MarketData. Until then this is random noise, flagged by
                # the warning at the top of this method and by is_synthetic_target
                # so no caller mistakes it for a real label.
                features['target_return'] = np.random.randn() * 0.02
                features['is_synthetic_target'] = 1

                data.append(features)

            except Exception as e:
                logger.error(f"Error processing impact score: {e}")
                continue

        df = pd.DataFrame(data)
        logger.info(f"Created dataset with {len(df)} samples")

        return df

    def get_feature_names(self) -> list[str]:
        """Get list of feature names for models."""
        return [
            'impact_score',
            'impact_confidence',
            'expected_volatility',
            'news_importance',
            'regime_sensitivity',
            'sector_sensitivity',
            'surprise_factor',
            'sentiment_overall',
            'sentiment_confidence',
            'event_earnings',
            'event_ma',
            'event_regulation',
            'event_macro',
            'has_surprise',
            'surprise_magnitude',
            'surprise_direction',
            'regime_volatility_high',
            'regime_trend_bear',
            'regime_risk_off',
            'vix_level',
            'hour_of_day',
            'day_of_week'
        ]
