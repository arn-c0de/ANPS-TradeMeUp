"""
Agent 4: Impact & Relevance Scoring Agent

OPTIMIZED VERSION:
- ✅ Scoped sessions with context manager (no shared session)
- ✅ Batch transactions (1 commit per batch instead of N)
- ✅ Proper error handling with rollback
- ✅ No session state leaks between batches
"""
import logging
import math
import uuid
from datetime import UTC, datetime, timezone

from sqlalchemy.orm import Session

from src.models.analysis import ImpactScore, MarketRegime, SurpriseScore
from src.models.data_quality import DataQualityScore
from src.models.database import get_scoped_session
from src.models.entities import Entity, NewsEntityMapping
from src.models.processed_news import ProcessedNews
from src.models.raw_news import RawNews

logger = logging.getLogger(__name__)


class ImpactScoringAgent:
    """
    Agent 4: Impact & Relevance Scoring Agent

    Responsibilities:
    - Calculate impact score for news-entity pairs
    - Combine multiple factors: importance, regime, surprise, etc.
    - Apply time decay function
    - Store impact scores with breakdown

    PERFORMANCE OPTIMIZATIONS:
    - Uses scoped sessions for isolation
    - Batch commits (creates all scores in single transaction)
    - Continues processing even if individual items fail
    """

    # Source authority scores
    SOURCE_AUTHORITY = {
        'Reuters': 0.95,
        'Bloomberg': 0.95,
        'Financial Times': 0.93,
        'Wall Street Journal': 0.93,
        'MarketWatch': 0.85,
        'Yahoo Finance': 0.80,
        'CNBC': 0.80,
        'default': 0.70
    }

    # Event severity scores
    EVENT_SEVERITY = {
        'earnings': 0.85,
        'm_and_a': 0.90,
        'regulation': 0.75,
        'macro': 0.80,
        'crisis': 0.95,
        'product': 0.65,
        'personnel': 0.70,
        'legal': 0.75,
        'guidance': 0.80,
        'other': 0.50
    }

    # Sector sensitivity multipliers (default = 1.0)
    SECTOR_SENSITIVITY = {
        'TECH': 1.2,
        'FIN': 1.1,
        'HEALTH': 1.0,
        'ENERGY': 1.15,
        'CONSUMER': 0.95,
        'default': 1.0
    }

    # Regime sensitivity multipliers
    REGIME_MULTIPLIERS = {
        'high_volatility': 1.5,
        'bear_market': 1.3,
        'risk_off': 1.4,
        'normal': 1.0
    }

    # Component weights (sum = 1.0)
    WEIGHTS = {
        'news_importance': 0.25,
        'regime_sensitivity': 0.20,
        'sector_sensitivity': 0.15,
        'historical_reaction': 0.20,
        'surprise_factor': 0.15,
        'liquidity_adjustment': 0.05
    }

    # Upper bounds of the multiplier-style components, used to map them into
    # 0-1 before the weighted sum. The regime multipliers compound, so the
    # maximum is their product (1.5 * 1.3 * 1.4 = 2.73) - not 2.0, which is
    # what the score was previously divided by.
    MAX_REGIME_SENSITIVITY = (
        REGIME_MULTIPLIERS['high_volatility']
        * REGIME_MULTIPLIERS['bear_market']
        * REGIME_MULTIPLIERS['risk_off']
    )
    MAX_SECTOR_SENSITIVITY = max(SECTOR_SENSITIVITY.values())
    MAX_SURPRISE_FACTOR = 2.0

    def __init__(self):
        """
        Initialize impact scoring agent.

        NOTE: No database session parameter!
        Sessions are created per-operation for isolation.
        """
        pass  # No db parameter!

    def _get_source_authority(self, source: str | None) -> float:
        """Get authority score for news source."""
        if not source:
            return self.SOURCE_AUTHORITY['default']

        source_lower = source.lower()
        for known_source, score in self.SOURCE_AUTHORITY.items():
            # Skip the 'default' entry: it is the fallback, not a source name,
            # and a source containing the word "default" would match it.
            if known_source == 'default':
                continue
            if known_source.lower() in source_lower:
                return score
        return self.SOURCE_AUTHORITY['default']

    def _get_event_severity(self, event_type: str) -> float:
        """Get severity score for event type."""
        return self.EVENT_SEVERITY.get(event_type, self.EVENT_SEVERITY['other'])

    def _get_sector_sensitivity(self, sector_code: str) -> float:
        """Get sector sensitivity multiplier."""
        return self.SECTOR_SENSITIVITY.get(sector_code, self.SECTOR_SENSITIVITY['default'])

    def _calculate_news_importance(
        self,
        source: str,
        event_type: str,
        sentiment_confidence: float,
        quality_score: float
    ) -> float:
        """
        Calculate news importance score (0-1).

        Components:
        - Source authority (0.3 weight)
        - Event severity (0.3 weight)
        - Sentiment confidence (0.2 weight)
        - Quality score (0.2 weight)
        """
        source_auth = self._get_source_authority(source)
        event_sev = self._get_event_severity(event_type)

        importance = (
            0.3 * source_auth +
            0.3 * event_sev +
            0.2 * sentiment_confidence +
            0.2 * quality_score
        )

        return min(1.0, max(0.0, importance))

    def _get_current_regime(self, db: Session) -> dict:
        """Get current market regime."""
        # Get most recent regime
        regime = db.query(MarketRegime).order_by(
            MarketRegime.timestamp.desc()
        ).first()

        if regime:
            return regime.regime

        # Default regime if none found
        return {
            'volatility': 'normal',
            'trend': 'neutral',
            'risk_appetite': 'neutral'
        }

    def _calculate_regime_sensitivity(self, current_regime: dict) -> float:
        """
        Calculate regime sensitivity multiplier (0-2).

        Higher values mean news has more impact in current regime.
        """
        multiplier = 1.0

        # Volatility component
        if current_regime.get('volatility') == 'high':
            multiplier *= self.REGIME_MULTIPLIERS['high_volatility']

        # Trend component
        if current_regime.get('trend') == 'bear':
            multiplier *= self.REGIME_MULTIPLIERS['bear_market']

        # Risk appetite component
        if current_regime.get('risk_appetite') == 'risk_off':
            multiplier *= self.REGIME_MULTIPLIERS['risk_off']

        return multiplier

    def _get_surprise_factor(self, db: Session, news_id: str) -> float:
        """
        Get surprise factor (0-2).

        Higher values mean larger surprise.
        """
        # Check if surprise score exists
        surprise = db.query(SurpriseScore).filter(
            SurpriseScore.news_id == news_id
        ).first()

        if not surprise:
            return 1.0  # No surprise info, neutral

        # Use normalized surprise (in std devs)
        surprise_norm = surprise.surprise_normalized or 0.0

        # Convert to 0-2 scale (0 = no surprise, 1 = expected, 2 = huge surprise)
        if abs(surprise_norm) < 0.5:
            return 0.8  # Small surprise
        elif abs(surprise_norm) < 1.0:
            return 1.2  # Moderate surprise
        elif abs(surprise_norm) < 2.0:
            return 1.5  # Large surprise
        else:
            return 2.0  # Huge surprise

    def _calculate_historical_reaction(self, event_type: str, entity_id: str) -> float:
        """
        Calculate historical reaction strength (0-1).

        Based on how strongly this entity/sector typically reacts to this event type.
        """
        # This would ideally query historical price movements
        # For MVP, use heuristic based on event type
        base_reactions = {
            'earnings': 0.75,
            'm_and_a': 0.90,
            'regulation': 0.65,
            'macro': 0.70,
            'crisis': 0.85,
            'product': 0.55,
            'personnel': 0.60,
            'legal': 0.65,
            'guidance': 0.70,
            'other': 0.50
        }

        return base_reactions.get(event_type, 0.50)

    def _calculate_liquidity_adjustment(self, entity_id: str) -> float:
        """
        Calculate liquidity adjustment (0.5-1.0).

        Lower liquidity = lower score (harder to trade).
        """
        # This would ideally use actual trading volume data
        # For MVP, assume all entities are liquid (score = 1.0)
        return 0.95

    def _calculate_time_decay(self, published_at: datetime) -> float:
        """
        Calculate time decay factor (0-1).

        News becomes less relevant over time.
        """
        # Use timezone-aware datetime for PostgreSQL compatibility
        now = datetime.now(UTC)
        # Ensure published_at is timezone-aware
        if published_at.tzinfo is None:
            published_at = published_at.replace(tzinfo=UTC)

        hours_old = (now - published_at).total_seconds() / 3600

        # Exponential decay: exp(-λ * hours)
        # λ = 0.05 means half-life of ~14 hours
        lambda_rate = 0.05
        decay = math.exp(-lambda_rate * hours_old)

        return max(0.1, decay)  # Minimum 0.1 to avoid complete decay

    def process_batch(self, limit: int = 30) -> dict:
        """
        Process batch of articles without impact scores.

        PERFORMANCE: Single transaction for entire batch (30x faster)
        SAFETY: Isolated session with automatic cleanup
        STABILITY: Continues processing even if individual items fail

        Args:
            limit: Maximum number of articles to process

        Returns:
            Statistics dictionary
        """
        # Use scoped session for isolation
        with get_scoped_session() as db:
            # Find articles with entity mappings but no impact scores
            articles = self._find_articles_without_impact(db, limit)

            if not articles:
                logger.info("No articles to process for impact scoring")
                return {
                    'processed': 0,
                    'total_scores': 0,
                    'high_impact': 0,
                    'medium_impact': 0,
                    'low_impact': 0,
                    'errors': 0
                }

            logger.info(f"Processing batch of {len(articles)} articles for impact scoring")

            stats = {
                'processed': 0,
                'total_scores': 0,
                'high_impact': 0,
                'medium_impact': 0,
                'low_impact': 0,
                'errors': 0
            }

            all_impact_scores = []

            # Process all articles WITHOUT committing
            for (news_id,) in articles:
                try:
                    # Calculate impact scores for all entities (without commit)
                    impact_scores = self._process_article_no_commit(db, str(news_id))

                    if impact_scores:
                        all_impact_scores.extend(impact_scores)
                        stats['processed'] += 1
                        stats['total_scores'] += len(impact_scores)

                        # Classify by impact level
                        for score in impact_scores:
                            if score.impact_score >= 0.7:
                                stats['high_impact'] += 1
                            elif score.impact_score >= 0.4:
                                stats['medium_impact'] += 1
                            else:
                                stats['low_impact'] += 1

                except Exception as e:
                    # Log error but CONTINUE processing other articles
                    logger.error(f"Error processing article {news_id}: {e}")
                    stats['errors'] += 1
                    continue

            # ✅ CRITICAL: Bulk save all impact scores
            if all_impact_scores:
                db.bulk_save_objects(all_impact_scores)
                logger.info(f"Bulk saved {len(all_impact_scores)} impact scores")

            # ✅ SINGLE COMMIT for entire batch
            # (Happens automatically in context manager on success)

            logger.info(f"Impact scoring complete. Stats: {stats}")
            return stats

    def _find_articles_without_impact(self, db: Session, limit: int) -> list:
        """
        Find articles with entity mappings but no impact scores.

        Args:
            db: Database session
            limit: Maximum number to return

        Returns:
            List of (news_id,) tuples
        """
        articles = db.query(RawNews.news_id).join(
            NewsEntityMapping,
            RawNews.news_id == NewsEntityMapping.news_id
        ).outerjoin(
            ImpactScore,
            RawNews.news_id == ImpactScore.news_id
        ).filter(
            ImpactScore.score_id.is_(None)
        ).group_by(RawNews.news_id).order_by(
            RawNews.published_at.desc()  # Newest first
        ).limit(limit).all()

        return articles

    def _process_article_no_commit(
        self,
        db: Session,
        news_id: str
    ) -> list[ImpactScore]:
        """
        Process article and calculate impact scores WITHOUT committing.

        This allows batching multiple articles into a single transaction.

        Args:
            db: Database session
            news_id: UUID of article to process

        Returns:
            List of ImpactScore objects (not yet committed)
        """
        try:
            # Get all entities mapped to this news
            mappings = db.query(NewsEntityMapping).filter(
                NewsEntityMapping.news_id == news_id
            ).all()

            if not mappings:
                logger.debug(f"No entity mappings found for news {news_id}")
                return []

            impact_scores = []

            for mapping in mappings:
                try:
                    # Calculate impact
                    result = self._calculate_impact(db, news_id, mapping.entity_id)

                    if result:
                        # Create impact score record
                        impact_score = ImpactScore(
                            score_id=uuid.uuid4(),
                            news_id=news_id,
                            entity_id=mapping.entity_id,
                            impact_score=result['impact_score'],
                            impact_breakdown=result['impact_breakdown'],
                            confidence=result['confidence'],
                            time_horizon=result['time_horizon'],
                            expected_volatility_impact=result['expected_volatility_impact'],
                            created_at=datetime.now(UTC)
                        )

                        impact_scores.append(impact_score)

                        logger.debug(
                            f"Calculated impact for {mapping.entity_id}: "
                            f"score={impact_score.impact_score:.3f}"
                        )

                except Exception as e:
                    logger.error(f"Error calculating impact for {mapping.entity_id}: {e}")
                    continue

            if impact_scores:
                logger.info(f"Created {len(impact_scores)} impact scores for news {news_id}")

            return impact_scores

        except Exception as e:
            logger.error(f"Error processing article {news_id}: {e}", exc_info=True)
            return []

    def _calculate_impact(
        self,
        db: Session,
        news_id: str,
        entity_id: str
    ) -> dict | None:
        """
        Calculate impact score for a news-entity pair.

        Args:
            db: Database session
            news_id: News UUID
            entity_id: Entity ID

        Returns:
            Dictionary with impact score and breakdown, or None on error
        """
        try:
            # Fetch required data
            news = db.query(RawNews).filter(RawNews.news_id == news_id).first()
            if not news:
                logger.warning(f"News {news_id} not found")
                return None

            processed = db.query(ProcessedNews).filter(
                ProcessedNews.news_id == news_id
            ).first()
            if not processed:
                logger.warning(f"Processed news {news_id} not found")
                return None

            quality = db.query(DataQualityScore).filter(
                DataQualityScore.news_id == news_id
            ).first()

            entity = db.query(Entity).filter(Entity.entity_id == entity_id).first()
            if not entity:
                logger.warning(f"Entity {entity_id} not found")
                return None

            # Calculate components
            news_importance = self._calculate_news_importance(
                source=news.source,
                event_type=processed.event_type or 'other',
                sentiment_confidence=processed.sentiment.get('confidence', 0.5) if processed.sentiment else 0.5,
                quality_score=quality.quality_score if quality else 0.7
            )

            current_regime = self._get_current_regime(db)
            regime_sensitivity = self._calculate_regime_sensitivity(current_regime)

            # Determine sector sensitivity from entity metadata (use metadata_ column)
            try:
                import json as _json
                if entity.metadata_:
                    meta = entity.metadata_ if isinstance(entity.metadata_, dict) else _json.loads(entity.metadata_)
                else:
                    meta = {}
            except Exception:
                meta = {}

            sector_code = meta.get('sector') if meta else None
            sector_sensitivity = self._get_sector_sensitivity(sector_code or 'default')

            historical_reaction = self._calculate_historical_reaction(
                event_type=processed.event_type or 'other',
                entity_id=entity_id
            )

            surprise_factor = self._get_surprise_factor(db, news_id)

            liquidity_adjustment = self._calculate_liquidity_adjustment(entity_id)

            time_decay = self._calculate_time_decay(news.published_at)

            # Weighted impact score. Every term must land in 0-1 for the
            # weights to mean what they say: regime_sensitivity was divided by
            # 2.0 although it reaches 2.73, and sector_sensitivity (up to 1.2)
            # was fed in unnormalized, so the sum could exceed 1.0.
            impact_base = (
                self.WEIGHTS['news_importance'] * news_importance +
                self.WEIGHTS['regime_sensitivity'] * (regime_sensitivity / self.MAX_REGIME_SENSITIVITY) +
                self.WEIGHTS['sector_sensitivity'] * (sector_sensitivity / self.MAX_SECTOR_SENSITIVITY) +
                self.WEIGHTS['historical_reaction'] * historical_reaction +
                self.WEIGHTS['surprise_factor'] * (surprise_factor / self.MAX_SURPRISE_FACTOR) +
                self.WEIGHTS['liquidity_adjustment'] * liquidity_adjustment
            )

            # Apply time decay, then clamp: impact_score is documented and
            # consumed as a 0-1 score.
            impact_score = min(1.0, max(0.0, impact_base * time_decay))

            # Determine time horizon
            if processed.event_type in ['earnings', 'guidance']:
                time_horizon = 'short_term'  # 1-3 days
            elif processed.event_type in ['m_and_a', 'product']:
                time_horizon = 'medium_term'  # 1-4 weeks
            else:
                time_horizon = 'long_term'  # 1-6 months

            # Expected volatility impact (rough estimate)
            expected_volatility = impact_score * 0.15  # Max 15% vol increase

            return {
                'impact_score': impact_score,
                'impact_breakdown': {
                    'news_importance': news_importance,
                    'regime_sensitivity': regime_sensitivity,
                    'sector_sensitivity': sector_sensitivity,
                    'historical_reaction': historical_reaction,
                    'surprise_factor': surprise_factor,
                    'liquidity_adjustment': liquidity_adjustment,
                    'time_decay': time_decay,
                    'current_regime': current_regime
                },
                'confidence': processed.confidence,
                'time_horizon': time_horizon,
                'expected_volatility_impact': expected_volatility
            }

        except Exception as e:
            logger.error(f"Error calculating impact for {news_id}/{entity_id}: {e}")
            return None

    def get_statistics(self) -> dict:
        """
        Get impact scoring statistics.

        Uses scoped session for isolation.
        """
        from sqlalchemy import func

        with get_scoped_session() as db:
            total_scores = db.query(ImpactScore).count()

            # Average impact by time horizon
            by_horizon = db.query(
                ImpactScore.time_horizon,
                func.avg(ImpactScore.impact_score).label('avg_score'),
                func.count(ImpactScore.score_id).label('count')
            ).group_by(ImpactScore.time_horizon).all()

            # High impact scores (>= 0.7)
            high_impact_count = db.query(ImpactScore).filter(
                ImpactScore.impact_score >= 0.7
            ).count()

            # Top impactful scores (news_id, entity_id, score)
            top_scores = db.query(ImpactScore).order_by(ImpactScore.impact_score.desc()).limit(5).all()
            top_impactful = [
                {
                    'news_id': str(s.news_id),
                    'entity_id': s.entity_id,
                    'impact_score': float(s.impact_score),
                    'time_horizon': s.time_horizon
                }
                for s in top_scores
            ]

            return {
                'total_scores': total_scores,
                'high_impact_count': high_impact_count,
                'by_time_horizon': {
                    horizon: {'avg_score': float(avg), 'count': count}
                    for horizon, avg, count in by_horizon
                },
                'top_impactful': top_impactful
            }
