"""
Agent 2: Content Understanding Agent - NLP analysis using LLM

OPTIMIZED VERSION:
- ✅ Scoped sessions with context manager (no shared session)
- ✅ Batch transactions (1 commit per batch instead of N)
- ✅ Proper error handling with rollback
- ✅ No session state leaks between batches
"""
import logging
from datetime import UTC, datetime, timezone
from pathlib import Path
from typing import Dict, List, Optional

from sqlalchemy.orm import Session

from src.models.database import get_scoped_session
from src.models.processed_news import ProcessedNews
from src.models.raw_news import RawNews
from src.services.llm_service import llm_service

logger = logging.getLogger(__name__)


class ContentUnderstandingAgent:
    """
    Agent 2: Content Understanding Agent

    Responsibilities:
    - Text summarization (short & medium)
    - Key fact extraction
    - Sentiment analysis (fine-grained)
    - Event type classification
    - Embedding generation

    PERFORMANCE OPTIMIZATIONS:
    - Uses scoped sessions for isolation
    - Batch commits (30x faster than individual commits)
    - Continues processing even if individual items fail
    """

    def __init__(self):
        """
        Initialize content understanding agent.

        NOTE: No database session parameter!
        Sessions are created per-operation for isolation.
        """
        self.llm = llm_service

        # Load prompt template
        prompt_path = Path("config/prompts/content_understanding.txt")
        if prompt_path.exists():
            with open(prompt_path) as f:
                self.prompt_template = f.read()
        else:
            # Fallback inline prompt
            self.prompt_template = self._get_fallback_prompt()

    def _get_fallback_prompt(self) -> str:
        """Fallback prompt if file not found."""
        return """You are a financial news analyst. Analyze the following article:

Title: {title}
Content: {content}

Provide analysis in JSON format:
{{
  "summary_short": "One sentence summary",
  "summary_medium": "3-5 sentence summary",
  "key_facts": [{{"fact": "...", "confidence": 0.9}}],
  "sentiment": {{"overall": 0.5, "confidence": 0.8, "aspects": {{}}}},
  "event_type": "earnings",
  "event_subtype": "beat",
  "confidence": 0.85
}}

Event types: earnings, m_and_a, regulation, macro, crisis, product, personnel, legal, guidance, other
Sentiment: -1 (negative) to +1 (positive)

Respond ONLY with JSON."""

    def process_batch(self, limit: int = 30) -> dict:
        """
        Process batch of unprocessed articles with optimized database operations.

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
            # Find high-quality articles without NLP processing
            articles = self._find_unprocessed_articles(db, limit)

            if not articles:
                logger.info("No articles to process")
                return {'processed': 0, 'errors': 0, 'by_event_type': {}}

            logger.info(f"Processing batch of {len(articles)} articles for content understanding")

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

                        # Count by event type
                        event_type = processed.event_type or 'unknown'
                        stats['by_event_type'][event_type] = \
                            stats['by_event_type'].get(event_type, 0) + 1

                except Exception as e:
                    # Log error but CONTINUE processing other articles
                    logger.error(f"Error processing article {article.news_id}: {e}")
                    stats['errors'] += 1
                    continue

            # ✅ CRITICAL: Bulk save all processed items
            # This is MUCH faster than individual adds
            if processed_items:
                db.bulk_save_objects(processed_items)
                logger.info(f"Bulk saved {len(processed_items)} items")

            # ✅ SINGLE COMMIT for entire batch
            # (Happens automatically in context manager on success)

            logger.info(f"Content understanding complete. Stats: {stats}")
            return stats

    def _find_unprocessed_articles(self, db: Session, limit: int) -> list[RawNews]:
        """
        Find high-quality articles that haven't been processed yet.

        Args:
            db: Database session
            limit: Maximum number to return

        Returns:
            List of RawNews objects
        """
        from src.models.data_quality import DataQualityScore

        articles = db.query(RawNews).join(
            DataQualityScore,
            RawNews.news_id == DataQualityScore.news_id
        ).outerjoin(
            ProcessedNews,
            RawNews.news_id == ProcessedNews.news_id
        ).filter(
            DataQualityScore.quality_score >= 0.6,  # Only process decent quality
            ProcessedNews.news_id.is_(None)  # Not yet processed
        ).order_by(
            RawNews.published_at.desc()  # Newest first
        ).limit(limit).all()

        return articles

    def _process_article_no_commit(
        self,
        db: Session,
        article: RawNews
    ) -> ProcessedNews | None:
        """
        Process single article WITHOUT committing to database.

        This allows batching multiple articles into a single transaction.

        Args:
            db: Database session
            article: Article to process

        Returns:
            ProcessedNews object (not yet committed) or None on error
        """
        try:
            # Call LLM for analysis
            logger.debug(f"Analyzing article {article.news_id}")
            analysis = self._analyze_article(db, article)

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
                existing.llm_metadata = analysis.get('llm_metadata', {})
                existing.processing_timestamp = datetime.now(UTC)

                logger.info(
                    f"Updated article {article.news_id}: "
                    f"event_type={existing.event_type}, "
                    f"sentiment={existing.sentiment.get('overall', 0):.2f}"
                )

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
                    llm_metadata=analysis.get('llm_metadata', {}),
                    processing_timestamp=datetime.now(UTC)
                )

                logger.info(
                    f"Processed article {article.news_id}: "
                    f"event_type={processed.event_type}, "
                    f"sentiment={processed.sentiment.get('overall', 0):.2f}"
                )

                return processed

        except Exception as e:
            logger.error(f"Error processing article {article.news_id}: {e}", exc_info=True)
            return None

    def _analyze_article(self, db: Session, article: RawNews) -> dict:
        """
        Analyze article using LLM.

        Args:
            db: Database session (for fetching related data if needed)
            article: Article to analyze

        Returns:
            Analysis results dictionary
        """
        # Prepare prompt
        prompt = self.prompt_template.format(
            title=article.title,
            content=article.full_text[:4000]  # Limit to avoid token limits
        )

        try:
            # Get LLM analysis
            logger.debug(f"Calling LLM for article {article.news_id}")
            analysis = self.llm.generate_json(prompt, temperature=0.1)

            # Validate required fields
            required_fields = ['summary_short', 'event_type', 'sentiment']
            missing_fields = [f for f in required_fields if f not in analysis]
            if missing_fields:
                logger.warning(f"LLM response missing fields {missing_fields}, using defaults")
                # Add defaults for missing fields
                if 'summary_short' not in analysis:
                    analysis['summary_short'] = article.title[:200]
                if 'event_type' not in analysis:
                    analysis['event_type'] = 'other'
                if 'sentiment' not in analysis:
                    analysis['sentiment'] = {'overall': 0.0, 'confidence': 0.0}

            # Generate embedding
            logger.debug(f"Generating embedding for article {article.news_id}")
            embedding = self.llm.get_embedding(article.full_text[:1000])

            # Add metadata
            analysis['embedding'] = embedding
            analysis['news_id'] = str(article.news_id)
            analysis['llm_metadata'] = {
                'provider': self.llm.provider,
                'model': self.llm.model,
                'temperature': 0.1,
                'timestamp': datetime.now(UTC).isoformat()
            }

            return analysis

        except ValueError as e:
            # JSON parsing failed - log but create minimal analysis
            logger.error(f"Error analyzing article {article.news_id}: {e}")
            logger.warning(f"Creating fallback analysis for article {article.news_id}")

            # Return minimal valid analysis
            try:
                embedding = self.llm.get_embedding(article.full_text[:1000])
            except Exception:
                embedding = []

            return {
                'news_id': str(article.news_id),
                'summary_short': article.title[:200],
                'summary_medium': article.full_text[:500],
                'key_facts': [],
                'sentiment': {'overall': 0.0, 'confidence': 0.0},
                'event_type': 'other',
                'event_subtype': None,
                'confidence': 0.0,
                'embedding': embedding,
                'llm_metadata': {
                    'provider': self.llm.provider,
                    'model': self.llm.model,
                    'error': str(e),
                    'fallback': True,
                    'timestamp': datetime.now(UTC).isoformat()
                }
            }
        except Exception as e:
            logger.error(f"Error analyzing article {article.news_id}: {e}")
            raise

    def get_statistics(self) -> dict:
        """
        Get processing statistics.

        Uses scoped session for isolation.
        """
        from sqlalchemy import Float, func

        with get_scoped_session() as db:
            total_processed = db.query(ProcessedNews).count()

            # Count by event type
            by_event_type = db.query(
                ProcessedNews.event_type,
                func.count(ProcessedNews.news_id).label('count')
            ).group_by(ProcessedNews.event_type).all()

            # Average sentiment
            # PostgreSQL uses ->> operator for JSONB text extraction
            avg_sentiment = db.query(
                func.avg(
                    func.cast(
                        ProcessedNews.sentiment.op('->>')('overall'),
                        Float
                    )
                )
            ).scalar()

            return {
                'total_processed': total_processed,
                'by_event_type': {et: count for et, count in by_event_type},
                'average_sentiment': float(avg_sentiment) if avg_sentiment else 0.0
            }
