"""Feature engineering for prediction models."""
import logging
from datetime import UTC, datetime

import pandas as pd
from sqlalchemy.orm import Session

from src.models.analysis import ImpactScore, MarketRegime, SurpriseScore
from src.models.processed_news import ProcessedNews
from src.services.market_data import market_data
from src.utils.prediction_math import FLAT_RETURN_TOLERANCE_PCT

logger = logging.getLogger(__name__)


class FeatureEngineer:
    """Feature engineering for ML models."""

    # Cap on rows pulled into a training dataset (MVP limit).
    MAX_TRAINING_SAMPLES = 100

    # History window fetched per ticker when labelling training samples.
    TRAINING_HISTORY_PERIOD = "1y"

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
        logger.info(f"Creating training dataset from {start_date} to {end_date}")

        data = []
        skipped_no_label = 0

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

        # One price history per ticker for the whole build, rather than one
        # lookup per sample.
        price_history: dict[str, pd.DataFrame | None] = {}

        for impact in impact_scores[:self.MAX_TRAINING_SAMPLES]:
            try:
                # Label first: a sample without a realised outcome is not
                # training data, and computing features for it is wasted work.
                target_return = self._forward_return(
                    ticker=impact.entity_id,
                    as_of_date=impact.created_at,
                    horizon_days=horizon_days,
                    price_history=price_history,
                )
                if target_return is None:
                    skipped_no_label += 1
                    continue

                features = self.extract_features_for_prediction(
                    entity_id=impact.entity_id,
                    news_id=str(impact.news_id),
                    as_of_date=impact.created_at
                )

                # Add identifiers
                features['news_id'] = str(impact.news_id)
                features['entity_id'] = impact.entity_id
                features['timestamp'] = impact.created_at

                # Realised return over the horizon, as a decimal fraction
                features['target_return'] = target_return
                features['target_direction'] = self._return_to_direction(target_return)

                data.append(features)

            except Exception as e:
                logger.error(f"Error processing impact score: {e}")
                continue

        df = pd.DataFrame(data)
        logger.info(
            "Created dataset with %d samples (%d skipped: no realised %dd outcome yet)",
            len(df),
            skipped_no_label,
            horizon_days,
        )

        return df

    def _return_to_direction(self, return_fraction: float) -> str:
        """Bucket a realised return into the up/flat/down label space.

        The band matches FLAT_RETURN_TOLERANCE_PCT used when scoring
        predictions, so training labels and evaluation agree on what "flat"
        means.
        """
        threshold = FLAT_RETURN_TOLERANCE_PCT / 100.0
        if return_fraction > threshold:
            return 'up'
        if return_fraction < -threshold:
            return 'down'
        return 'flat'

    def _get_price_history(
        self,
        ticker: str,
        price_history: dict,
    ) -> pd.DataFrame | None:
        """Fetch (and memoise) a ticker's daily bars with a naive UTC index."""
        if ticker in price_history:
            return price_history[ticker]

        frame = None
        try:
            raw = market_data.get_historical_data(
                ticker, period=self.TRAINING_HISTORY_PERIOD, interval="1d"
            )
            if raw is not None and not raw.empty:
                # get_historical_data hands back a copy, so localizing the
                # index here cannot corrupt the shared cache.
                index = raw.index
                if getattr(index, "tz", None) is not None:
                    raw.index = index.tz_convert("UTC").tz_localize(None)
                frame = raw
        except Exception as e:
            logger.debug(f"No price history for {ticker}: {e}")

        price_history[ticker] = frame
        return frame

    def _forward_return(
        self,
        ticker: str,
        as_of_date: datetime,
        horizon_days: int,
        price_history: dict,
    ) -> float | None:
        """Realised return from ``as_of_date`` over ``horizon_days`` sessions.

        No look-ahead: ``searchsorted(side='left')`` picks the first bar at or
        after the news timestamp, so the entry close always lies in the future
        relative to the news. News during a session is entered at that
        session's close; news after the close is entered at the next session's.

        Returns None when the ticker has no usable history, or when the
        horizon has not elapsed yet - an unlabelled sample is dropped rather
        than guessed at.
        """
        history = self._get_price_history(ticker, price_history)
        if history is None or 'Close' not in history.columns:
            return None

        as_of = as_of_date
        if getattr(as_of, "tzinfo", None) is not None:
            as_of = as_of.astimezone(UTC).replace(tzinfo=None)

        # First session at or after the news, so the entry price is one the
        # trade could actually have been filled at.
        entry_positions = history.index.searchsorted(as_of, side='left')
        entry_index = int(entry_positions)
        exit_index = entry_index + horizon_days

        # exit_index out of range means the horizon has not completed yet
        if entry_index >= len(history) or exit_index >= len(history):
            return None

        entry_price = history.iloc[entry_index]['Close']
        exit_price = history.iloc[exit_index]['Close']

        if not entry_price or entry_price <= 0 or exit_price is None:
            return None

        return float((exit_price - entry_price) / entry_price)

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
