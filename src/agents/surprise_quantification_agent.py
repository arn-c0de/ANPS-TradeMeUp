"""Agent 4.5: Surprise Quantification Agent."""
import logging
import re
import uuid
from datetime import UTC, datetime, timezone
from typing import Dict, List, Optional

import numpy as np
from sqlalchemy.orm import Session

from src.models.analysis import SurpriseScore
from src.models.entities import NewsEntityMapping
from src.models.processed_news import ProcessedNews
from src.models.raw_news import RawNews

logger = logging.getLogger(__name__)


class SurpriseQuantificationAgent:
    """
    Agent 4.5: Surprise Quantification Agent

    Responsibilities:
    - Extract actual values from news (EPS, revenue, etc.)
    - Compare to consensus estimates
    - Calculate surprise magnitude
    - Normalize surprises
    """

    # Patterns to extract financial metrics
    METRIC_PATTERNS = {
        'eps': [
            r'EPS[:\s]+\$?([\d.]+)',
            r'earnings per share[:\s]+\$?([\d.]+)',
            r'reported[:\s]+\$?([\d.]+)[:\s]+per share',
        ],
        'revenue': [
            r'revenue[:\s]+\$?([\d.]+)\s*(billion|million|B|M)',
            r'sales[:\s]+\$?([\d.]+)\s*(billion|million|B|M)',
        ],
        'guidance': [
            r'guidance[:\s]+\$?([\d.]+)',
            r'forecast[:\s]+\$?([\d.]+)',
        ]
    }

    # Historical standard deviations (placeholder - should be calculated from data)
    HISTORICAL_STD = {
        'eps': 0.10,  # $0.10 typical surprise
        'revenue': 500,  # $500M typical surprise
        'guidance': 0.15
    }

    def __init__(self):
        """
        Initialize surprise quantification agent.
        
        Note: Uses scoped sessions internally for better isolation.
        """
        pass

    def _extract_metric(self, text: str, metric_name: str) -> float | None:
        """
        Extract financial metric from text using regex.

        Args:
            text: Text to search
            metric_name: Metric to extract (eps, revenue, guidance)

        Returns:
            Extracted value or None
        """
        patterns = self.METRIC_PATTERNS.get(metric_name, [])

        for pattern in patterns:
            match = re.search(pattern, text, re.IGNORECASE)
            if match:
                try:
                    value_str = match.group(1)
                    value = float(value_str)

                    # Handle billions/millions for revenue
                    if metric_name == 'revenue' and len(match.groups()) > 1:
                        unit = match.group(2).lower()
                        if unit in ['billion', 'b']:
                            value *= 1000  # Convert to millions
                        # else already in millions

                    return value
                except ValueError:
                    continue

        return None

    def _get_consensus_estimate(
        self,
        entity_id: str,
        metric: str,
        as_of_date: datetime
    ) -> float | None:
        """
        Get consensus estimate for entity/metric.

        In production, this would query analyst_expectations table.
        For MVP, return None (no consensus data).

        Args:
            entity_id: Entity ticker
            metric: Metric name
            as_of_date: Date for estimate

        Returns:
            Consensus value or None
        """
        # TODO: Implement when analyst_expectations table is populated
        # For now, return None to skip surprise calculation
        return None

    def _calculate_surprise_normalized(
        self,
        actual: float,
        consensus: float,
        metric: str
    ) -> float:
        """
        Calculate normalized surprise in standard deviations.

        Args:
            actual: Actual reported value
            consensus: Consensus estimate
            metric: Metric name

        Returns:
            Surprise in std devs
        """
        surprise_raw = actual - consensus
        std_dev = self.HISTORICAL_STD.get(metric, 1.0)

        surprise_normalized = surprise_raw / std_dev
        return surprise_normalized

    def _estimate_market_priced_in(
        self,
        surprise_normalized: float
    ) -> float:
        """
        Estimate how much of the surprise was already priced in.

        This would ideally use options implied volatility.
        For MVP, use heuristic.

        Args:
            surprise_normalized: Surprise in std devs

        Returns:
            Portion already priced in (0-1)
        """
        # Heuristic: Larger surprises are less priced in
        if abs(surprise_normalized) > 2.0:
            return 0.1  # Only 10% priced in for huge surprises
        elif abs(surprise_normalized) > 1.0:
            return 0.3  # 30% priced in for large surprises
        else:
            return 0.5  # 50% priced in for moderate surprises

    def _determine_expected_reaction(
        self,
        surprise_normalized: float
    ) -> str:
        """
        Determine expected market reaction based on surprise.

        Args:
            surprise_normalized: Surprise in std devs

        Returns:
            Reaction description
        """
        if surprise_normalized > 2.0:
            return "positive_strong"
        elif surprise_normalized > 1.0:
            return "positive_moderate"
        elif surprise_normalized > 0.3:
            return "positive_weak"
        elif surprise_normalized < -2.0:
            return "negative_strong"
        elif surprise_normalized < -1.0:
            return "negative_moderate"
        elif surprise_normalized < -0.3:
            return "negative_weak"
        else:
            return "neutral"

    def calculate_surprise(
        self,
        actual: float,
        expected: float,
        metric_name: str = 'eps'
    ) -> dict:
        """
        Calculate surprise score.

        Args:
            actual: Actual reported value
            expected: Expected/consensus value
            metric_name: Type of metric (eps, revenue, etc.)

        Returns:
            Dictionary with surprise details
        """
        if expected == 0:
            return {
                'surprise_raw': 0,
                'surprise_normalized': 0,
                'magnitude': 'none'
            }

        surprise_raw = actual - expected
        surprise_pct = (surprise_raw / abs(expected)) * 100

        # Normalize by historical std
        std = self.HISTORICAL_STD.get(metric_name, 0.1)
        surprise_normalized = surprise_raw / std if std > 0 else 0

        # Determine magnitude
        abs_norm = abs(surprise_normalized)
        if abs_norm > 2.0:
            magnitude = 'extreme'
        elif abs_norm > 1.0:
            magnitude = 'large'
        elif abs_norm > 0.3:
            magnitude = 'moderate'
        else:
            magnitude = 'small'

        return {
            'surprise_raw': surprise_raw,
            'surprise_pct': surprise_pct,
            'surprise_normalized': surprise_normalized,
            'magnitude': magnitude,
            'expected_reaction': self._determine_expected_reaction(surprise_normalized)
        }

    def analyze_article(self, db: Session, news_id: str) -> list[dict]:
        """
        Analyze article for surprises.

        Args:
            db: Database session
            news_id: UUID of article

        Returns:
            List of surprise analysis results
        """
        # Fetch article and processed data
        news = db.query(RawNews).filter(RawNews.news_id == news_id).first()
        if not news:
            raise ValueError(f"News {news_id} not found")

        processed = db.query(ProcessedNews).filter(
            ProcessedNews.news_id == news_id
        ).first()

        # Only analyze earnings-related news
        if not processed or processed.event_type not in ['earnings', 'guidance']:
            logger.debug(f"News {news_id} is not earnings-related, skipping surprise analysis")
            return []

        # Get entities
        mappings = db.query(NewsEntityMapping).filter(
            NewsEntityMapping.news_id == news_id,
            NewsEntityMapping.exposure_type == 'direct'
        ).all()

        if not mappings:
            logger.debug(f"No direct entity mappings for {news_id}")
            return []

        surprises = []

        # Extract metrics from text
        full_text = news.title + "\n" + news.full_text

        for metric_name in ['eps', 'revenue', 'guidance']:
            actual_value = self._extract_metric(full_text, metric_name)

            if actual_value is None:
                continue

            # For each entity
            for mapping in mappings:
                # Get consensus (would query database in production)
                consensus = self._get_consensus_estimate(
                    mapping.entity_id,
                    metric_name,
                    news.published_at
                )

                if consensus is None:
                    # No consensus data available
                    # For MVP, create a surprise record with limited info
                    surprises.append({
                        'entity_id': mapping.entity_id,
                        'metric': metric_name,
                        'actual': actual_value,
                        'consensus': None,
                        'surprise_raw': None,
                        'surprise_normalized': None,
                        'surprise_percentile': None,
                        'market_priced_in': None,
                        'true_surprise': None,
                        'expected_reaction': 'unknown'
                    })
                    logger.info(
                        f"Found {metric_name}={actual_value} for {mapping.entity_id}, "
                        f"but no consensus available"
                    )
                else:
                    # Calculate surprise
                    surprise_raw = actual_value - consensus
                    surprise_normalized = self._calculate_surprise_normalized(
                        actual_value,
                        consensus,
                        metric_name
                    )

                    # Estimate what was priced in
                    market_priced_in = self._estimate_market_priced_in(surprise_normalized)
                    true_surprise = surprise_raw * (1 - market_priced_in)

                    # Calculate percentile (placeholder - would use historical data)
                    surprise_percentile = 0.5 + (surprise_normalized / 6.0)  # Rough approximation
                    surprise_percentile = max(0.0, min(1.0, surprise_percentile))

                    expected_reaction = self._determine_expected_reaction(surprise_normalized)

                    surprises.append({
                        'entity_id': mapping.entity_id,
                        'metric': metric_name,
                        'actual': actual_value,
                        'consensus': consensus,
                        'surprise_raw': surprise_raw,
                        'surprise_normalized': surprise_normalized,
                        'surprise_percentile': surprise_percentile,
                        'market_priced_in': market_priced_in,
                        'true_surprise': true_surprise,
                        'expected_reaction': expected_reaction
                    })

                    logger.info(
                        f"Surprise for {mapping.entity_id} {metric_name}: "
                        f"actual={actual_value}, consensus={consensus}, "
                        f"normalized={surprise_normalized:.2f} std devs"
                    )

        return surprises

    def _process_article_no_commit(self, db: Session, news_id: str) -> list[SurpriseScore]:
        """
        Process article without committing (for batch operations).

        Args:
            db: Database session
            news_id: UUID of article

        Returns:
            List of SurpriseScore objects (not yet committed)
        """
        surprises = self.analyze_article(db, news_id)

        surprise_scores = []

        for surprise in surprises:
            score = SurpriseScore(
                surprise_id=uuid.uuid4(),
                news_id=news_id,
                metric=surprise['metric'],
                actual=surprise['actual'],
                consensus=surprise['consensus'],
                surprise_raw=surprise['surprise_raw'],
                surprise_normalized=surprise['surprise_normalized'],
                surprise_percentile=surprise['surprise_percentile'],
                market_priced_in=surprise['market_priced_in'],
                true_surprise=surprise['true_surprise'],
                expected_reaction=surprise['expected_reaction'],
                created_at=datetime.now(UTC)
            )
            surprise_scores.append(score)

        return surprise_scores

    def process_article(self, news_id: str) -> list[SurpriseScore]:
        """
        Process article and save surprise scores.
        
        DEPRECATED: Use process_batch() for better performance.

        Args:
            news_id: UUID of article

        Returns:
            List of SurpriseScore objects
        """
        from src.models.database import get_scoped_session

        with get_scoped_session() as db:
            try:
                surprise_scores = self._process_article_no_commit(db, news_id)

                if surprise_scores:
                    db.add_all(surprise_scores)
                    logger.info(f"Created {len(surprise_scores)} surprise scores for news {news_id}")

                return surprise_scores

            except Exception as e:
                logger.error(f"Error processing surprises for {news_id}: {e}")
                raise

    def process_batch(self, limit: int = 20) -> dict:
        """
        Process batch of earnings news for surprises with optimized single transaction.

        Args:
            limit: Maximum number of articles to process

        Returns:
            Statistics dictionary
        """
        from src.models.database import get_scoped_session

        with get_scoped_session() as db:
            # Find earnings news without surprise scores
            articles = db.query(RawNews.news_id).join(
                ProcessedNews,
                RawNews.news_id == ProcessedNews.news_id
            ).outerjoin(
                SurpriseScore,
                RawNews.news_id == SurpriseScore.news_id
            ).filter(
                ProcessedNews.event_type.in_(['earnings', 'guidance']),
                SurpriseScore.surprise_id.is_(None)
            ).order_by(
                RawNews.published_at.desc()  # Newest first
            ).limit(limit).all()

            logger.info(f"Processing {len(articles)} articles for surprise quantification")

            stats = {
                'processed': 0,
                'surprises_found': 0,
                'with_consensus': 0,
                'without_consensus': 0,
                'errors': 0
            }

            all_surprise_scores = []

            for (news_id,) in articles:
                try:
                    surprise_scores = self._process_article_no_commit(db, str(news_id))
                    stats['processed'] += 1
                    stats['surprises_found'] += len(surprise_scores)

                    for score in surprise_scores:
                        if score.consensus is not None:
                            stats['with_consensus'] += 1
                        else:
                            stats['without_consensus'] += 1

                    all_surprise_scores.extend(surprise_scores)

                except Exception as e:
                    stats['errors'] += 1
                    logger.error(f"Error processing {news_id}: {e}")
                    continue

            # Bulk save all surprise scores
            if all_surprise_scores:
                db.bulk_save_objects(all_surprise_scores)

            logger.info(f"Surprise quantification complete. Stats: {stats}")
            return stats

    def get_statistics(self) -> dict:
        """Get surprise statistics."""
        from sqlalchemy import func

        from src.models.database import get_scoped_session

        with get_scoped_session() as db:
            total_surprises = db.query(SurpriseScore).count()

            # Count by metric
            by_metric = db.query(
                SurpriseScore.metric,
                func.count(SurpriseScore.surprise_id).label('count')
            ).group_by(SurpriseScore.metric).all()

            # Average surprise magnitude
            avg_surprise = db.query(
                func.avg(func.abs(SurpriseScore.surprise_normalized))
            ).scalar()

            # Largest surprises
            top_surprises = db.query(
                SurpriseScore.news_id,
                SurpriseScore.metric,
                SurpriseScore.surprise_normalized,
                SurpriseScore.expected_reaction
            ).filter(
                SurpriseScore.surprise_normalized.isnot(None)
            ).order_by(
                func.abs(SurpriseScore.surprise_normalized).desc()
            ).limit(10).all()

            return {
                'total_surprises': total_surprises,
                'by_metric': {metric: count for metric, count in by_metric},
                'avg_surprise_magnitude': float(avg_surprise) if avg_surprise else 0.0,
                'top_surprises': [
                    {
                        'news_id': str(nid),
                        'metric': metric,
                        'surprise_std_devs': float(surprise),
                        'expected_reaction': reaction
                    }
                    for nid, metric, surprise, reaction in top_surprises
                ]
            }
