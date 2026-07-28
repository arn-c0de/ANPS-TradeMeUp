"""Agent 5.5: Signal Decay Modeling Agent - Model how news impact decays over time."""
import logging
import math
from datetime import UTC, datetime, timedelta, timezone
from typing import Dict, Optional

from sqlalchemy import func
from sqlalchemy.orm import Session

from src.models.analysis import ImpactScore, SignalDecayModel
from src.models.raw_news import RawNews

logger = logging.getLogger(__name__)


class SignalDecayAgent:
    """
    Agent 5.5: Signal Decay Modeling Agent

    Responsibilities:
    - Model news signal decay over time
    - Calculate half-life of different event types
    - Adjust impact scores based on time elapsed
    - Identify when news becomes "stale"
    """

    # Event-specific decay parameters (days)
    EVENT_HALF_LIVES = {
        'earnings': 3.0,  # Earnings impact decays fast
        'guidance': 7.0,  # Guidance lasts longer
        'M&A': 14.0,  # M&A news has lasting impact
        'legal': 21.0,  # Legal issues linger
        'crisis': 10.0,  # Crises decay medium-term
        'product': 15.0,  # Product launches have medium impact
        'macro': 30.0,  # Macro news has long-lasting effects
        'regulation': 60.0,  # Regulatory changes very long-lasting
        'personnel': 5.0,  # Personnel changes short-lived
        'default': 7.0  # Default half-life
    }

    def __init__(self):
        """
        Initialize signal decay agent.
        
        Note: Uses scoped sessions internally for better isolation.
        """
        pass

    def calculate_decay(
        self,
        initial_impact: float,
        time_elapsed_hours: float,
        event_type: str = 'default',
        model_type: str = 'exponential'
    ) -> float:
        """
        Calculate decayed impact score.

        Args:
            initial_impact: Original impact score
            time_elapsed_hours: Hours since news published
            event_type: Type of event (affects decay rate)
            model_type: Decay model (exponential, power_law)

        Returns:
            Decayed impact score
        """
        half_life_days = self.EVENT_HALF_LIVES.get(event_type, self.EVENT_HALF_LIVES['default'])
        half_life_hours = half_life_days * 24

        if model_type == 'exponential':
            # Exponential decay: I(t) = I_0 * e^(-λt)
            # λ = ln(2) / half_life
            decay_rate = math.log(2) / half_life_hours
            decayed_impact = initial_impact * math.exp(-decay_rate * time_elapsed_hours)

        elif model_type == 'power_law':
            # Power law decay: I(t) = I_0 / (1 + t/τ)^α
            # τ = half_life, α = 2
            alpha = 2.0
            tau = half_life_hours
            decayed_impact = initial_impact / ((1 + time_elapsed_hours / tau) ** alpha)

        else:
            raise ValueError(f"Unknown model type: {model_type}")

        return max(0.0, decayed_impact)  # Ensure non-negative

    def _model_decay_no_commit(self, db: Session, news_id: str, impact_score: float) -> SignalDecayModel:
        """
        Create signal decay model without committing (for batch operations).

        Args:
            db: Database session
            news_id: UUID of news article
            impact_score: Initial impact score

        Returns:
            SignalDecayModel object (not yet committed)
        """
        # Fetch article to get event type
        from src.models.processed_news import ProcessedNews

        processed = db.query(ProcessedNews).filter(
            ProcessedNews.news_id == news_id
        ).first()

        event_type = processed.event_type if processed else 'default'

        # Get event-specific parameters
        half_life_days = self.EVENT_HALF_LIVES.get(event_type, self.EVENT_HALF_LIVES['default'])
        decay_rate_per_day = math.log(2) / half_life_days

        # Effective window: time until impact < 5% of original
        # e^(-λt) = 0.05 → t = -ln(0.05) / λ
        effective_window_days = int(-math.log(0.05) / decay_rate_per_day)

        # Create model
        decay_model = SignalDecayModel(
            news_id=news_id,
            initial_impact=impact_score,
            decay_rate=decay_rate_per_day,
            half_life_days=half_life_days,
            effective_window_days=effective_window_days,
            model_type='exponential',
            created_at=datetime.now(UTC)
        )

        logger.info(
            f"Created decay model for {news_id}: "
            f"half_life={half_life_days:.1f}d, window={effective_window_days}d"
        )

        return decay_model

    def model_decay(self, news_id: str, impact_score: float) -> SignalDecayModel:
        """
        Create signal decay model for a news article.
        
        DEPRECATED: Use process_batch() for better performance.

        Args:
            news_id: UUID of news article
            impact_score: Initial impact score

        Returns:
            SignalDecayModel object
        """
        from src.models.database import get_scoped_session

        with get_scoped_session() as db:
            decay_model = self._model_decay_no_commit(db, news_id, impact_score)
            db.merge(decay_model)  # Use merge for upsert
            return decay_model

    def get_current_impact(self, news_id: str) -> float | None:
        """
        Get current (time-adjusted) impact of a news article.

        Args:
            news_id: UUID of news article

        Returns:
            Current impact score or None
        """
        from src.models.database import get_scoped_session

        with get_scoped_session() as db:
            # Fetch decay model
            decay_model = db.query(SignalDecayModel).filter(
                SignalDecayModel.news_id == news_id
            ).first()

            if not decay_model:
                logger.warning(f"No decay model found for {news_id}")
                return None

            # Fetch news to get published time
            article = db.query(RawNews).filter(
                RawNews.news_id == news_id
            ).first()

            if not article:
                return None

            # Calculate time elapsed
            now = datetime.now(UTC)
            time_elapsed = now - article.published_at
            hours_elapsed = time_elapsed.total_seconds() / 3600

            # Calculate decayed impact
            current_impact = self.calculate_decay(
                initial_impact=decay_model.initial_impact,
                time_elapsed_hours=hours_elapsed,
                model_type=decay_model.model_type
            )

            return current_impact

    def process_batch(self, limit: int = 50) -> dict:
        """
        Process batch of impact scores and create decay models with optimized single transaction.

        Args:
            limit: Maximum number to process

        Returns:
            Statistics dictionary
        """
        from src.models.database import get_scoped_session

        with get_scoped_session() as db:
            # Find impact scores without decay models
            impact_scores = db.query(ImpactScore).outerjoin(
                SignalDecayModel,
                ImpactScore.news_id == SignalDecayModel.news_id
            ).filter(
                SignalDecayModel.news_id.is_(None)
            ).order_by(
                ImpactScore.created_at.desc()
            ).limit(limit).all()

            logger.info(f"Creating decay models for {len(impact_scores)} impact scores")

            stats = {
                'processed': 0,
                'avg_half_life': 0.0,
                'avg_window': 0.0,
                'errors': 0
            }

            half_lives = []
            windows = []
            decay_models = []

            for score in impact_scores:
                try:
                    model = self._model_decay_no_commit(
                        db,
                        news_id=str(score.news_id),
                        impact_score=score.impact_score
                    )
                    decay_models.append(model)
                    stats['processed'] += 1
                    half_lives.append(model.half_life_days)
                    windows.append(model.effective_window_days)

                except Exception as e:
                    stats['errors'] += 1
                    logger.error(f"Error creating decay model for {score.news_id}: {e}")
                    continue

            # Bulk save all decay models (using merge for upsert behavior)
            if decay_models:
                for model in decay_models:
                    db.merge(model)

            if half_lives:
                stats['avg_half_life'] = sum(half_lives) / len(half_lives)
                stats['avg_window'] = sum(windows) / len(windows)

            logger.info(f"Signal decay modeling complete. Stats: {stats}")
            return stats

    def get_statistics(self) -> dict:
        """Get signal decay statistics."""
        from src.models.database import get_scoped_session

        with get_scoped_session() as db:
            total_models = db.query(SignalDecayModel).count()

            if total_models == 0:
                return {
                    'total_models': 0,
                    'avg_half_life': 0.0,
                    'avg_window': 0.0,
                    'by_event_type': {}
                }

            # Average half-life
            avg_half_life = db.query(
                func.avg(SignalDecayModel.half_life_days)
            ).scalar() or 0.0

            # Average effective window
            avg_window = db.query(
                func.avg(SignalDecayModel.effective_window_days)
            ).scalar() or 0.0

            return {
                'total_models': total_models,
                'avg_half_life': float(avg_half_life),
                'avg_window': float(avg_window),
                'configured_half_lives': self.EVENT_HALF_LIVES
            }

    def cleanup_stale_signals(self, threshold_days: int = 90) -> int:
        """
        Clean up very old signal decay models.

        Args:
            threshold_days: Remove models older than this

        Returns:
            Number of records removed
        """
        from src.models.database import get_scoped_session

        with get_scoped_session() as db:
            cutoff = datetime.now(UTC) - timedelta(days=threshold_days)

            deleted = db.query(SignalDecayModel).filter(
                SignalDecayModel.created_at < cutoff
            ).delete()

            logger.info(f"Cleaned up {deleted} stale signal decay models")

            return deleted
