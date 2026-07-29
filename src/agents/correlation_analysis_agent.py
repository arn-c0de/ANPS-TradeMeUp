"""Agent 5.6: Correlation Analysis Agent - Analyze entity correlations and relationships."""
import logging
from datetime import UTC, datetime, timedelta, timezone
from typing import Dict, List, Optional, Tuple

import numpy as np
from sqlalchemy import func
from sqlalchemy.orm import Session

from src.models.entities import Entity, EntityRelationship
from src.models.predictions import MarketData

logger = logging.getLogger(__name__)


class CorrelationAnalysisAgent:
    """
    Agent 5.6: Correlation Analysis Agent

    Responsibilities:
    - Calculate price correlations between entities
    - Identify sector and industry relationships
    - Track correlation changes over time
    - Detect unusual correlation patterns
    """

    def __init__(self):
        """
        Initialize correlation analysis agent.
        
        Note: Uses scoped sessions internally for better isolation.
        """
        self._correlation_cache = {}

    def calculate_price_correlation(
        self,
        db: Session,
        entity_1: str,
        entity_2: str,
        lookback_days: int = 90
    ) -> float | None:
        """
        Calculate price correlation between two entities.

        Args:
            db: Database session
            entity_1: First entity ID (ticker)
            entity_2: Second entity ID (ticker)
            lookback_days: Historical period for calculation

        Returns:
            Correlation coefficient (-1 to 1) or None
        """
        # Cache key
        cache_key = f"{entity_1}:{entity_2}:{lookback_days}"
        if cache_key in self._correlation_cache:
            return self._correlation_cache[cache_key]

        cutoff = datetime.now(UTC) - timedelta(days=lookback_days)

        # Fetch price data for both entities. The column is `ticker`;
        # filtering on a non-existent `entity_id` raised AttributeError and
        # made every correlation calculation fail.
        data_1 = db.query(MarketData).filter(
            MarketData.ticker == entity_1,
            MarketData.timestamp >= cutoff
        ).order_by(MarketData.timestamp).all()

        data_2 = db.query(MarketData).filter(
            MarketData.ticker == entity_2,
            MarketData.timestamp >= cutoff
        ).order_by(MarketData.timestamp).all()

        if len(data_1) < 20 or len(data_2) < 20:
            logger.warning(f"Insufficient data for correlation: {entity_1}, {entity_2}")
            return None

        # Calculate returns, skipping bars with a non-positive close so a bad
        # tick cannot raise ZeroDivisionError mid-series.
        returns_1 = self._close_to_returns(data_1)
        returns_2 = self._close_to_returns(data_2)

        # Align data (take minimum length)
        min_len = min(len(returns_1), len(returns_2))
        returns_1 = returns_1[:min_len]
        returns_2 = returns_2[:min_len]

        if min_len < 20:
            return None

        # Calculate correlation
        try:
            correlation = np.corrcoef(returns_1, returns_2)[0, 1]
            if np.isnan(correlation):
                # A constant series has zero variance, so corrcoef is undefined
                logger.debug(f"Undefined correlation for {entity_1}/{entity_2} (flat series)")
                return None
            self._correlation_cache[cache_key] = float(correlation)
            return float(correlation)
        except Exception as e:
            logger.error(f"Error calculating correlation: {e}")
            return None

    @staticmethod
    def _close_to_returns(bars: list) -> list[float]:
        """Convert a series of bars into simple close-to-close returns."""
        returns = []
        for previous, current in zip(bars, bars[1:]):
            if previous.close and previous.close > 0 and current.close is not None:
                returns.append((current.close - previous.close) / previous.close)
        return returns

    def analyze_entity_relationships(
        self,
        db: Session,
        entity_id: str,
        min_correlation: float = 0.5
    ) -> list[dict]:
        """
        Analyze relationships for a specific entity.

        Args:
            db: Database session
            entity_id: Entity to analyze
            min_correlation: Minimum correlation threshold

        Returns:
            List of related entities with correlation scores
        """
        # Get all other entities
        all_entities = db.query(Entity).filter(
            Entity.entity_id != entity_id,
            Entity.entity_type == 'company'
        ).all()

        relationships = []

        for other_entity in all_entities:
            correlation = self.calculate_price_correlation(
                db,
                entity_id,
                other_entity.entity_id,
                lookback_days=90
            )

            if correlation is not None and abs(correlation) >= min_correlation:
                relationships.append({
                    'entity_id': other_entity.entity_id,
                    'entity_name': other_entity.entity_name,
                    'correlation': correlation,
                    'relationship_type': 'positive' if correlation > 0 else 'negative'
                })

        # Sort by absolute correlation
        relationships.sort(key=lambda x: abs(x['correlation']), reverse=True)

        return relationships

    def update_entity_relationships(self, entity_id: str) -> int:
        """
        Update entity relationship records in database.

        Args:
            entity_id: Entity to update relationships for

        Returns:
            Number of relationships updated
        """
        from src.models.database import get_scoped_session

        with get_scoped_session() as db:
            logger.info(f"Updating relationships for {entity_id}")

            relationships = self.analyze_entity_relationships(db, entity_id, min_correlation=0.4)

            # Delete existing relationships
            db.query(EntityRelationship).filter(
                EntityRelationship.entity_1 == entity_id
            ).delete()

            # Create new relationships
            relationship_objects = []
            for rel in relationships[:20]:  # Top 20 correlations
                relationship = EntityRelationship(
                    entity_1=entity_id,
                    entity_2=rel['entity_id'],
                    relationship_type='correlation',
                    strength=abs(rel['correlation']),
                    direction='positive' if rel['correlation'] > 0 else 'negative',
                    metadata={'lookback_days': 90},
                    created_at=datetime.now(UTC)
                )
                relationship_objects.append(relationship)

            # Bulk save
            if relationship_objects:
                db.bulk_save_objects(relationship_objects)

            logger.info(f"Updated {len(relationship_objects)} relationships for {entity_id}")

            return len(relationship_objects)

    def detect_correlation_anomalies(
        self,
        db: Session,
        entity_1: str,
        entity_2: str,
        window_days: int = 30
    ) -> dict:
        """
        Detect unusual correlation patterns.

        Args:
            db: Database session
            entity_1: First entity
            entity_2: Second entity
            window_days: Rolling window for anomaly detection

        Returns:
            Anomaly detection results
        """
        # Calculate correlation over different timeframes
        corr_30d = self.calculate_price_correlation(db, entity_1, entity_2, 30)
        corr_90d = self.calculate_price_correlation(db, entity_1, entity_2, 90)
        corr_180d = self.calculate_price_correlation(db, entity_1, entity_2, 180)

        if None in [corr_30d, corr_90d, corr_180d]:
            return {
                'anomaly_detected': False,
                'reason': 'insufficient_data'
            }

        # Check for correlation breakdown
        corr_change_30_90 = abs(corr_30d - corr_90d)
        corr_change_90_180 = abs(corr_90d - corr_180d)

        # Threshold: change > 0.3 is anomalous
        if corr_change_30_90 > 0.3 or corr_change_90_180 > 0.3:
            return {
                'anomaly_detected': True,
                'type': 'correlation_breakdown',
                'corr_30d': corr_30d,
                'corr_90d': corr_90d,
                'corr_180d': corr_180d,
                'change_30_90': corr_change_30_90,
                'severity': 'high' if corr_change_30_90 > 0.5 else 'medium'
            }

        return {
            'anomaly_detected': False,
            'corr_30d': corr_30d,
            'corr_90d': corr_90d,
            'corr_180d': corr_180d
        }

    def process_batch(self, limit: int = 10) -> dict:
        """
        Process batch of entities for correlation analysis.

        Args:
            limit: Maximum number of entities to process

        Returns:
            Statistics dictionary
        """
        from src.models.database import get_scoped_session
        from src.models.entities import NewsEntityMapping

        with get_scoped_session() as db:
            # Get top entities by mention count
            top_entities = db.query(
                NewsEntityMapping.entity_id,
                func.count(NewsEntityMapping.mapping_id).label('mentions')
            ).join(
                Entity,
                NewsEntityMapping.entity_id == Entity.entity_id
            ).filter(
                Entity.entity_type == 'company'
            ).group_by(
                NewsEntityMapping.entity_id
            ).order_by(
                func.count(NewsEntityMapping.mapping_id).desc()
            ).limit(limit).all()

            logger.info(f"Analyzing correlations for {len(top_entities)} entities")

            stats = {
                'entities_processed': 0,
                'total_relationships': 0,
                'avg_relationships_per_entity': 0.0,
                'errors': 0
            }

            total_relationships = 0

            # Note: Each entity gets its own scoped session via update_entity_relationships
            for entity_id, mentions in top_entities:
                try:
                    count = self.update_entity_relationships(entity_id)
                    stats['entities_processed'] += 1
                    total_relationships += count

                except Exception as e:
                    stats['errors'] += 1
                    logger.error(f"Error analyzing correlations for {entity_id}: {e}")
                    continue

            if stats['entities_processed'] > 0:
                stats['total_relationships'] = total_relationships
                stats['avg_relationships_per_entity'] = total_relationships / stats['entities_processed']

            logger.info(f"Correlation analysis complete. Stats: {stats}")
            return stats

    def get_statistics(self) -> dict:
        """Get correlation analysis statistics."""
        from src.models.database import get_scoped_session

        with get_scoped_session() as db:
            total_relationships = db.query(EntityRelationship).filter(
                EntityRelationship.relationship_type == 'correlation'
            ).count()

            if total_relationships == 0:
                return {
                    'total_relationships': 0,
                    'avg_strength': 0.0,
                    'positive_count': 0,
                    'negative_count': 0
                }

            # Average correlation strength
            avg_strength = db.query(
                func.avg(EntityRelationship.strength)
            ).filter(
                EntityRelationship.relationship_type == 'correlation'
            ).scalar() or 0.0

            # Positive/negative counts
            positive = db.query(EntityRelationship).filter(
                EntityRelationship.relationship_type == 'correlation',
                EntityRelationship.direction == 'positive'
            ).count()

            negative = db.query(EntityRelationship).filter(
                EntityRelationship.relationship_type == 'correlation',
                EntityRelationship.direction == 'negative'
            ).count()

            return {
                'total_relationships': total_relationships,
                'avg_strength': float(avg_strength),
                'positive_count': positive,
                'negative_count': negative
            }
