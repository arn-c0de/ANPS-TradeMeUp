"""Agent 2: Content Understanding Agent - NLP analysis using LLM."""
import logging
from typing import Dict, Optional
from datetime import datetime
from pathlib import Path
from sqlalchemy.orm import Session
from sqlalchemy import func, Float

from src.models.raw_news import RawNews
from src.models.processed_news import ProcessedNews
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
    """

    def __init__(self, db: Session):
        """
        Initialize content understanding agent.

        Args:
            db: Database session
        """
        self.db = db
        self.llm = llm_service

        # Load prompt template
        prompt_path = Path("config/prompts/content_understanding.txt")
        if prompt_path.exists():
            with open(prompt_path, 'r') as f:
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

    def analyze_article(self, news_id: str) -> Dict:
        """
        Analyze article using LLM.

        Args:
            news_id: UUID of article to analyze

        Returns:
            Analysis results dictionary
        """
        # Fetch article
        article = self.db.query(RawNews).filter(
            RawNews.news_id == news_id
        ).first()

        if not article:
            raise ValueError(f"Article {news_id} not found")

        # Prepare prompt
        prompt = self.prompt_template.format(
            title=article.title,
            content=article.full_text[:4000]  # Limit to avoid token limits
        )

        try:
            # Get LLM analysis
            logger.info(f"Analyzing article {news_id} with {self.llm.provider}")
            analysis = self.llm.generate_json(prompt, temperature=0.1)

            # Generate embedding
            logger.info(f"Generating embedding for article {news_id}")
            embedding = self.llm.get_embedding(article.full_text[:1000])

            # Add metadata
            analysis['embedding'] = embedding
            analysis['news_id'] = str(news_id)
            analysis['llm_metadata'] = {
                'provider': self.llm.provider,
                'model': self.llm.model,
                'temperature': 0.1,
                'timestamp': datetime.utcnow().isoformat()
            }

            return analysis

        except Exception as e:
            logger.error(f"Error analyzing article {news_id}: {e}")
            raise

    def process_article(self, news_id: str) -> ProcessedNews:
        """
        Process article and save analysis to database.

        Args:
            news_id: UUID of article to process

        Returns:
            ProcessedNews object
        """
        try:
            # Analyze article
            analysis = self.analyze_article(news_id)

            # Create processed news record
            processed = ProcessedNews(
                news_id=analysis['news_id'],
                summary_short=analysis.get('summary_short'),
                summary_medium=analysis.get('summary_medium'),
                key_facts=analysis.get('key_facts', []),
                sentiment=analysis.get('sentiment', {}),
                event_type=analysis.get('event_type'),
                event_subtype=analysis.get('event_subtype'),
                confidence=analysis.get('confidence', 0.0),
                embedding=analysis.get('embedding', []),
                llm_metadata=analysis.get('llm_metadata', {}),
                processing_timestamp=datetime.utcnow()
            )

            # Check if record exists
            existing = self.db.query(ProcessedNews).filter(
                ProcessedNews.news_id == analysis['news_id']
            ).first()

            if existing:
                # Update existing
                existing.summary_short = analysis.get('summary_short')
                existing.summary_medium = analysis.get('summary_medium')
                existing.key_facts = analysis.get('key_facts', [])
                existing.sentiment = analysis.get('sentiment', {})
                existing.event_type = analysis.get('event_type')
                existing.event_subtype = analysis.get('event_subtype')
                existing.confidence = analysis.get('confidence', 0.0)
                existing.embedding = analysis.get('embedding', [])
                existing.llm_metadata = analysis.get('llm_metadata', {})
                existing.processing_timestamp = datetime.utcnow()
                processed = existing
            else:
                # Add new
                self.db.add(processed)
            
            self.db.commit()
            self.db.refresh(processed)

            logger.info(
                f"Processed article {news_id}: "
                f"event_type={processed.event_type}, "
                f"sentiment={processed.sentiment.get('overall', 0):.2f}"
            )

            return processed

        except Exception as e:
            self.db.rollback()
            logger.error(f"Error processing article {news_id}: {e}")
            raise

    def process_batch(self, limit: int = 10) -> Dict:
        """
        Process batch of unprocessed articles.

        Args:
            limit: Maximum number of articles to process

        Returns:
            Statistics dictionary
        """
        # Find high-quality articles without NLP processing
        from src.models.data_quality import DataQualityScore

        articles = self.db.query(RawNews).join(
            DataQualityScore,
            RawNews.news_id == DataQualityScore.news_id
        ).outerjoin(
            ProcessedNews,
            RawNews.news_id == ProcessedNews.news_id
        ).filter(
            DataQualityScore.quality_score >= 0.6,  # Only process decent quality
            ProcessedNews.news_id.is_(None)  # Not yet processed
        ).limit(limit).all()

        logger.info(f"Processing {len(articles)} articles for content understanding")

        stats = {
            'processed': 0,
            'by_event_type': {},
            'errors': 0
        }

        for article in articles:
            try:
                processed = self.process_article(str(article.news_id))
                stats['processed'] += 1

                # Count by event type
                event_type = processed.event_type or 'unknown'
                stats['by_event_type'][event_type] = stats['by_event_type'].get(event_type, 0) + 1

            except Exception as e:
                stats['errors'] += 1
                logger.error(f"Error processing article {article.news_id}: {e}")
                continue

        logger.info(f"Content understanding complete. Stats: {stats}")
        return stats

    def get_statistics(self) -> Dict:
        """Get processing statistics."""
        from sqlalchemy import func

        total_processed = self.db.query(ProcessedNews).count()

        # Count by event type
        by_event_type = self.db.query(
            ProcessedNews.event_type,
            func.count(ProcessedNews.news_id).label('count')
        ).group_by(ProcessedNews.event_type).all()

        # Average sentiment
        avg_sentiment = self.db.query(
            func.avg(
                func.cast(
                    func.json_extract(ProcessedNews.sentiment, '$.overall'),
                    Float
                )
            )
        ).scalar()

        return {
            'total_processed': total_processed,
            'by_event_type': {et: count for et, count in by_event_type},
            'average_sentiment': float(avg_sentiment) if avg_sentiment else 0.0
        }
