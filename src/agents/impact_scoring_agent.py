"""Agent 4: Impact & Relevance Scoring Agent."""
import logging
import math
from typing import Dict, Optional
from datetime import datetime, timedelta
import uuid
from sqlalchemy.orm import Session

from src.models.raw_news import RawNews
from src.models.processed_news import ProcessedNews
from src.models.entities import NewsEntityMapping, Entity
from src.models.analysis import ImpactScore, SurpriseScore, MarketRegime
from src.models.data_quality import DataQualityScore

logger = logging.getLogger(__name__)


class ImpactScoringAgent:
    """
    Agent 4: Impact & Relevance Scoring Agent

    Responsibilities:
    - Calculate impact score for news-entity pairs
    - Combine multiple factors: importance, regime, surprise, etc.
    - Apply time decay function
    - Store impact scores with breakdown
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

    def __init__(self, db: Session):
        """
        Initialize impact scoring agent.

        Args:
            db: Database session
        """
        self.db = db

    def _get_source_authority(self, source: str) -> float:
        """Get authority score for news source."""
        for known_source, score in self.SOURCE_AUTHORITY.items():
            if known_source.lower() in source.lower():
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

    def _get_current_regime(self) -> Dict:
        """Get current market regime."""
        # Get most recent regime
        regime = self.db.query(MarketRegime).order_by(
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

    def _calculate_regime_sensitivity(self, current_regime: Dict) -> float:
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

    def _get_surprise_factor(self, news_id: str) -> float:
        """
        Get surprise factor (0-2).

        Higher values mean larger surprise.
        """
        # Check if surprise score exists
        surprise = self.db.query(SurpriseScore).filter(
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
        hours_old = (datetime.utcnow() - published_at).total_seconds() / 3600

        # Exponential decay: exp(-λ * hours)
        # λ = 0.05 means half-life of ~14 hours
        lambda_rate = 0.05
        decay = math.exp(-lambda_rate * hours_old)

        return max(0.1, decay)  # Minimum 0.1 to avoid complete decay

    def calculate_impact(self, news_id: str, entity_id: str) -> Dict:
        """
        Calculate impact score for a news-entity pair.

        Returns:
            Dictionary with impact score and breakdown
        """
        # Fetch required data
        news = self.db.query(RawNews).filter(RawNews.news_id == news_id).first()
        if not news:
            raise ValueError(f"News {news_id} not found")

        processed = self.db.query(ProcessedNews).filter(
            ProcessedNews.news_id == news_id
        ).first()
        if not processed:
            raise ValueError(f"Processed news {news_id} not found")

        quality = self.db.query(DataQualityScore).filter(
            DataQualityScore.news_id == news_id
        ).first()

        entity = self.db.query(Entity).filter(Entity.entity_id == entity_id).first()
        if not entity:
            raise ValueError(f"Entity {entity_id} not found")

        # Calculate components
        news_importance = self._calculate_news_importance(
            source=news.source,
            event_type=processed.event_type or 'other',
            sentiment_confidence=processed.sentiment.get('confidence', 0.5) if processed.sentiment else 0.5,
            quality_score=quality.quality_score if quality else 0.7
        )

        current_regime = self._get_current_regime()
        regime_sensitivity = self._calculate_regime_sensitivity(current_regime)

        sector_code = entity.metadata.get('sector') if entity.metadata else None
        sector_sensitivity = self._get_sector_sensitivity(sector_code or 'default')

        historical_reaction = self._calculate_historical_reaction(
            event_type=processed.event_type or 'other',
            entity_id=entity_id
        )

        surprise_factor = self._get_surprise_factor(str(news_id))

        liquidity_adjustment = self._calculate_liquidity_adjustment(entity_id)

        time_decay = self._calculate_time_decay(news.published_at)

        # Calculate weighted impact score
        impact_base = (
            self.WEIGHTS['news_importance'] * news_importance +
            self.WEIGHTS['regime_sensitivity'] * (regime_sensitivity / 2.0) +  # Normalize to 0-1
            self.WEIGHTS['sector_sensitivity'] * sector_sensitivity +
            self.WEIGHTS['historical_reaction'] * historical_reaction +
            self.WEIGHTS['surprise_factor'] * (surprise_factor / 2.0) +  # Normalize to 0-1
            self.WEIGHTS['liquidity_adjustment'] * liquidity_adjustment
        )

        # Apply time decay
        impact_score = impact_base * time_decay

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

    def process_article(self, news_id: str) -> list[ImpactScore]:
        """
        Process article and calculate impact scores for all mapped entities.

        Args:
            news_id: UUID of article to process

        Returns:
            List of ImpactScore objects
        """
        try:
            # Get all entities mapped to this news
            mappings = self.db.query(NewsEntityMapping).filter(
                NewsEntityMapping.news_id == news_id
            ).all()

            if not mappings:
                logger.warning(f"No entity mappings found for news {news_id}")
                return []

            impact_scores = []

            for mapping in mappings:
                try:
                    # Calculate impact
                    result = self.calculate_impact(str(news_id), mapping.entity_id)

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
                        created_at=datetime.utcnow()
                    )

                    self.db.add(impact_score)
                    impact_scores.append(impact_score)

                    logger.info(
                        f"Calculated impact for {mapping.entity_id}: "
                        f"score={impact_score.impact_score:.3f}"
                    )

                except Exception as e:
                    logger.error(f"Error calculating impact for {mapping.entity_id}: {e}")
                    continue

            # Commit all impact scores
            self.db.commit()

            logger.info(f"Created {len(impact_scores)} impact scores for news {news_id}")
            return impact_scores

        except Exception as e:
            self.db.rollback()
            logger.error(f"Error processing article {news_id}: {e}")
            raise

    def process_batch(self, limit: int = 10) -> Dict:
        """
        Process batch of articles without impact scores.

        Args:
            limit: Maximum number of articles to process

        Returns:
            Statistics dictionary
        """
        # Find articles with entity mappings but no impact scores
        from sqlalchemy import func

        articles = self.db.query(RawNews.news_id).join(
            NewsEntityMapping,
            RawNews.news_id == NewsEntityMapping.news_id
        ).outerjoin(
            ImpactScore,
            RawNews.news_id == ImpactScore.news_id
        ).filter(
            ImpactScore.score_id.is_(None)
        ).group_by(RawNews.news_id).limit(limit).all()

        logger.info(f"Processing {len(articles)} articles for impact scoring")

        stats = {
            'processed': 0,
            'total_scores': 0,
            'high_impact': 0,
            'medium_impact': 0,
            'low_impact': 0,
            'errors': 0
        }

        for (news_id,) in articles:
            try:
                impact_scores = self.process_article(str(news_id))
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
                stats['errors'] += 1
                logger.error(f"Error processing article {news_id}: {e}")
                continue

        logger.info(f"Impact scoring complete. Stats: {stats}")
        return stats

    def get_statistics(self) -> Dict:
        """Get impact scoring statistics."""
        from sqlalchemy import func

        total_scores = self.db.query(ImpactScore).count()

        # Average impact score
        avg_impact = self.db.query(
            func.avg(ImpactScore.impact_score)
        ).scalar()

        # Count by impact level
        high = self.db.query(ImpactScore).filter(
            ImpactScore.impact_score >= 0.7
        ).count()

        medium = self.db.query(ImpactScore).filter(
            ImpactScore.impact_score >= 0.4,
            ImpactScore.impact_score < 0.7
        ).count()

        low = self.db.query(ImpactScore).filter(
            ImpactScore.impact_score < 0.4
        ).count()

        # Top impactful news
        top_news = self.db.query(
            ImpactScore.news_id,
            ImpactScore.entity_id,
            ImpactScore.impact_score
        ).order_by(
            ImpactScore.impact_score.desc()
        ).limit(10).all()

        return {
            'total_scores': total_scores,
            'average_impact': float(avg_impact) if avg_impact else 0.0,
            'high_impact': high,
            'medium_impact': medium,
            'low_impact': low,
            'top_impactful': [
                {
                    'news_id': str(nid),
                    'entity_id': eid,
                    'impact_score': float(score)
                }
                for nid, eid, score in top_news
            ]
        }
