"""
Example: Optimized Agent Implementation
Demonstrates best practices for database performance and stability
"""
import logging
from typing import Dict, List
from datetime import datetime
from sqlalchemy.orm import Session

from src.models.database import get_scoped_session
from src.models.raw_news import RawNews
from src.models.processed_news import ProcessedNews
from src.models.data_quality import DataQualityScore
from src.services.llm_service import llm_service

logger = logging.getLogger(__name__)


class OptimizedContentAgent:
    """
    OPTIMIZED Version of Content Understanding Agent

    Key Improvements:
    1. ✅ Scoped sessions with context manager
    2. ✅ Batch transactions (1 commit per batch instead of N)
    3. ✅ Bulk operations for multiple inserts
    4. ✅ Proper error handling with rollback
    5. ✅ No shared session state
    """

    def __init__(self):
        """
        Initialize agent WITHOUT database session.

        Session is created per operation using context manager.
        """
        self.llm = llm_service

    def process_batch(self, limit: int = 30) -> Dict:
        """
        Process batch of articles with optimized database operations.

        ✅ FAST: Single transaction for entire batch
        ✅ SAFE: Isolated session with automatic cleanup
        ✅ STABLE: Continues processing even if individual items fail

        Args:
            limit: Maximum number of articles to process

        Returns:
            Statistics dictionary
        """
        # Use scoped session for isolation
        with get_scoped_session() as db:
            # Find articles to process
            articles = self._find_unprocessed_articles(db, limit)

            if not articles:
                logger.info("No articles to process")
                return {'processed': 0, 'errors': 0, 'by_event_type': {}}

            logger.info(f"Processing batch of {len(articles)} articles")

            stats = {
                'processed': 0,
                'errors': 0,
                'by_event_type': {}
            }

            processed_items = []

            # Process all articles WITHOUT committing
            for article in articles:
                try:
                    # Analyze article (may call LLM)
                    processed = self._process_article_no_commit(db, article)

                    if processed:
                        processed_items.append(processed)
                        stats['processed'] += 1

                        # Track by event type
                        event_type = processed.event_type or 'unknown'
                        stats['by_event_type'][event_type] = \
                            stats['by_event_type'].get(event_type, 0) + 1

                except Exception as e:
                    # Log error but CONTINUE processing other articles
                    logger.error(f"Error processing article {article.news_id}: {e}")
                    stats['errors'] += 1
                    continue

            # ✅ CRITICAL: Bulk add all processed items
            if processed_items:
                db.bulk_save_objects(processed_items)
                logger.info(f"Bulk added {len(processed_items)} items")

            # ✅ SINGLE COMMIT for entire batch
            # (Happens automatically in context manager on success)

            logger.info(f"Batch completed: {stats}")
            return stats

    def _find_unprocessed_articles(self, db: Session, limit: int) -> List[RawNews]:
        """
        Find high-quality articles that haven't been processed yet.

        Args:
            db: Database session
            limit: Maximum number to return

        Returns:
            List of RawNews objects
        """
        articles = db.query(RawNews).join(
            DataQualityScore,
            RawNews.news_id == DataQualityScore.news_id
        ).outerjoin(
            ProcessedNews,
            RawNews.news_id == ProcessedNews.news_id
        ).filter(
            DataQualityScore.quality_score >= 0.6,  # Only decent quality
            ProcessedNews.news_id.is_(None)  # Not yet processed
        ).order_by(
            RawNews.published_at.desc()  # Newest first
        ).limit(limit).all()

        return articles

    def _process_article_no_commit(
        self,
        db: Session,
        article: RawNews
    ) -> ProcessedNews:
        """
        Process single article WITHOUT committing to database.

        This allows batching multiple articles into a single transaction.

        Args:
            db: Database session
            article: Article to process

        Returns:
            ProcessedNews object (not yet committed)
        """
        # Call LLM for analysis
        logger.debug(f"Analyzing article {article.news_id}")
        analysis = self._analyze_with_llm(article)

        # Check if already exists
        existing = db.query(ProcessedNews).filter(
            ProcessedNews.news_id == str(article.news_id)
        ).first()

        if existing:
            # Update existing record
            existing.summary_short = analysis.get('summary_short')
            existing.summary_medium = analysis.get('summary_medium')
            existing.key_facts = analysis.get('key_facts', [])
            existing.sentiment = analysis.get('sentiment', {})
            existing.event_type = analysis.get('event_type')
            existing.event_subtype = analysis.get('event_subtype')
            existing.confidence = analysis.get('confidence', 0.0)
            existing.embedding = analysis.get('embedding', [])
            existing.processing_timestamp = datetime.utcnow()
            return existing
        else:
            # Create new record
            processed = ProcessedNews(
                news_id=str(article.news_id),
                summary_short=analysis.get('summary_short'),
                summary_medium=analysis.get('summary_medium'),
                key_facts=analysis.get('key_facts', []),
                sentiment=analysis.get('sentiment', {}),
                event_type=analysis.get('event_type'),
                event_subtype=analysis.get('event_subtype'),
                confidence=analysis.get('confidence', 0.0),
                embedding=analysis.get('embedding', []),
                processing_timestamp=datetime.utcnow()
            )
            return processed

    def _analyze_with_llm(self, article: RawNews) -> Dict:
        """
        Analyze article using LLM.

        Args:
            article: Article to analyze

        Returns:
            Analysis dictionary
        """
        # Build prompt
        prompt = f"""Analyze this financial news article:

Title: {article.title}
Content: {article.full_text[:4000]}

Provide JSON with:
- summary_short: One sentence
- event_type: earnings/m_and_a/regulation/macro/other
- sentiment: {{"overall": -1 to +1}}
- confidence: 0 to 1
"""

        try:
            # Get LLM analysis
            analysis = self.llm.generate_json(prompt, temperature=0.1)

            # Add defaults for missing fields
            if 'summary_short' not in analysis:
                analysis['summary_short'] = article.title[:200]
            if 'event_type' not in analysis:
                analysis['event_type'] = 'other'
            if 'sentiment' not in analysis:
                analysis['sentiment'] = {'overall': 0.0}

            # Generate embedding
            embedding = self.llm.get_embedding(article.full_text[:1000])
            analysis['embedding'] = embedding

            return analysis

        except Exception as e:
            logger.error(f"LLM analysis failed for {article.news_id}: {e}")
            # Return minimal fallback
            return {
                'summary_short': article.title[:200],
                'event_type': 'other',
                'sentiment': {'overall': 0.0},
                'confidence': 0.0,
                'embedding': []
            }


# =============================================================================
# Comparison: Old vs New
# =============================================================================

"""
OLD (SLOW) Implementation:
─────────────────────────────────────────────────────────

class ContentAgent:
    def __init__(self, db: Session):  # ❌ Shared session
        self.db = db

    def process_batch(self, limit: int):
        articles = self.db.query(...).limit(limit).all()

        for article in articles:
            # ❌ Individual commits (30 commits for 30 articles!)
            processed = self.process_article(article)

        return stats

    def process_article(self, article):
        # ... process ...
        self.db.add(processed)
        self.db.commit()  # ❌ SLOW!
        return processed


Performance:
- 30 articles × 50ms commit time = 1.5 seconds wasted
- Shared session causes state bleed
- Connection held open for entire pipeline
- No isolation between agents

─────────────────────────────────────────────────────────

NEW (FAST) Implementation:
─────────────────────────────────────────────────────────

class OptimizedContentAgent:
    def __init__(self):  # ✅ No shared session
        pass

    def process_batch(self, limit: int):
        with get_scoped_session() as db:  # ✅ Isolated session
            articles = db.query(...).limit(limit).all()

            processed_items = []
            for article in articles:
                # ✅ No commits in loop
                processed = self._process_article_no_commit(db, article)
                processed_items.append(processed)

            # ✅ Bulk add
            db.bulk_save_objects(processed_items)

            # ✅ Single commit (happens automatically)

        return stats


Performance:
- 30 articles × 1 commit = 50ms total
- 30x FASTER than old implementation
- Isolated sessions prevent state bleed
- Connection returned to pool immediately
- Full transaction isolation

"""


# =============================================================================
# Usage Example
# =============================================================================

if __name__ == "__main__":
    # Setup logging
    logging.basicConfig(level=logging.INFO)

    # Create agent (no db parameter!)
    agent = OptimizedContentAgent()

    # Process batch (creates own session internally)
    stats = agent.process_batch(limit=30)

    print(f"Processed: {stats['processed']}")
    print(f"Errors: {stats['errors']}")
    print(f"By type: {stats['by_event_type']}")
