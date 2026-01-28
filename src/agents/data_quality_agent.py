"""Agent 1.5: Data Quality Agent - Validates and scores news quality."""
import logging
from typing import Dict, Optional, List
from datetime import datetime, timezone
from sqlalchemy.orm import Session
from langdetect import detect, LangDetectException

from src.models.raw_news import RawNews
from src.models.data_quality import DataQualityScore
from src.services.llm_service import llm_service

logger = logging.getLogger(__name__)


class DataQualityAgent:
    """
    Agent 1.5: Data Quality Agent

    Responsibilities:
    - Duplicate detection (content hash + embedding similarity)
    - Content validation (length, structure, language)
    - Source reliability scoring
    - Quality score calculation
    """

    # Source reliability scores (based on reputation)
    SOURCE_RELIABILITY = {
        'Reuters': 0.95,
        'Bloomberg': 0.95,
        'Financial Times': 0.93,
        'Wall Street Journal': 0.93,
        'Yahoo Finance': 0.85,
        'MarketWatch': 0.85,
        'CNBC': 0.82,
        'NewsAPI': 0.75,
        'default': 0.70
    }

    # Quality thresholds
    MIN_WORD_COUNT = 50
    MAX_WORD_COUNT = 10000
    SIMILARITY_THRESHOLD = 0.85  # For duplicate detection

    def __init__(self):
        """
        Initialize data quality agent.
        
        Note: Uses scoped sessions internally for better isolation.
        """
        pass

    def _count_words(self, text: str) -> int:
        """Count words in text."""
        return len(text.split())

    def _get_source_reliability(self, source: str) -> float:
        """
        Get reliability score for a news source.

        Args:
            source: Source name

        Returns:
            Reliability score (0-1)
        """
        # Try exact match
        if source in self.SOURCE_RELIABILITY:
            return self.SOURCE_RELIABILITY[source]

        # Try partial match
        for known_source, score in self.SOURCE_RELIABILITY.items():
            if known_source.lower() in source.lower():
                return score

        # Default score
        return self.SOURCE_RELIABILITY['default']

    def _detect_language(self, text: str) -> tuple[str, float]:
        """
        Detect language of text.

        Args:
            text: Text to analyze

        Returns:
            Tuple of (language_code, confidence)
        """
        try:
            lang = detect(text)
            confidence = 0.9  # langdetect doesn't provide confidence
            return lang, confidence
        except LangDetectException:
            logger.warning("Language detection failed, assuming English")
            return "en", 0.5

    def _check_duplicate_by_hash(self, db: Session, content_hash: str, news_id: str) -> Optional[str]:
        """
        Check if article is duplicate by content hash.

        Args:
            db: Database session
            content_hash: SHA-256 hash of content
            news_id: Current article ID

        Returns:
            UUID of duplicate article if found, None otherwise
        """
        duplicate = db.query(RawNews).filter(
            RawNews.content_hash == content_hash,
            RawNews.news_id != news_id
        ).first()

        if duplicate:
            logger.info(f"Duplicate detected by hash: {news_id} -> {duplicate.news_id}")
            return str(duplicate.news_id)

        return None

    def _check_duplicate_by_url(self, db: Session, url: str, news_id: str) -> Optional[str]:
        """
        Check if article is duplicate by URL.

        Args:
            db: Database session
            url: Article URL
            news_id: Current article ID

        Returns:
            UUID of duplicate article if found, None otherwise
        """
        duplicate = db.query(RawNews).filter(
            RawNews.url == url,
            RawNews.news_id != news_id
        ).first()

        if duplicate:
            logger.info(f"Duplicate detected by URL: {news_id} -> {duplicate.news_id}")
            return str(duplicate.news_id)

        return None

    def calculate_quality_score(self, article: RawNews) -> float:
        """Calculate quality score for an article."""
        score = 0.0
        
        # Source reliability (0-35 points)
        source_reliability = self._get_source_reliability(article.source)
        score += source_reliability * 35
        
        # Content length (0-25 points)
        word_count = self._count_words(article.full_text)
        if word_count >= self.MIN_WORD_COUNT:
            length_score = min(word_count / 500, 1.0) * 25
            score += length_score
        
        # Has title (0-10 points)
        if article.title and len(article.title) > 10:
            score += 10
        
        # Has URL (0-10 points)
        if article.url and article.url.startswith('http'):
            score += 10
        
        # Published date (0-10 points)
        if article.published_at:
            score += 10
        
        # Language detection (0-10 points)
        try:
            detected_lang, confidence = self._detect_language(article.full_text)
            if detected_lang == 'en' and confidence > 0.8:
                score += 10
        except:
            pass
        
        return min(score / 100, 1.0)  # Normalize to 0-1

    def validate_article(self, db: Session, news_id: str) -> Dict:
        """
        Validate a single article and calculate quality score.

        Args:
            db: Database session
            news_id: UUID of the article to validate

        Returns:
            Dictionary with validation results
        """
        # Fetch article
        article = db.query(RawNews).filter(
            RawNews.news_id == news_id
        ).first()

        if not article:
            raise ValueError(f"Article {news_id} not found")

        validation_flags = {}
        quality_issues = []

        # Calculate quality score
        quality_score = self.calculate_quality_score(article)
        validation_flags['quality_score'] = quality_score
        quality_components = []

        # 1. Word count validation
        word_count = self._count_words(article.full_text)
        validation_flags['word_count_ok'] = (
            self.MIN_WORD_COUNT <= word_count <= self.MAX_WORD_COUNT
        )
        if not validation_flags['word_count_ok']:
            quality_issues.append(f"Word count {word_count} outside range [{self.MIN_WORD_COUNT}, {self.MAX_WORD_COUNT}]")
            quality_components.append(0.3)
        else:
            quality_components.append(1.0)

        # 2. Language detection
        detected_lang, lang_confidence = self._detect_language(article.full_text)
        validation_flags['language_ok'] = (detected_lang == 'en' and lang_confidence > 0.6)
        validation_flags['detected_language'] = detected_lang
        if not validation_flags['language_ok']:
            quality_issues.append(f"Language {detected_lang} with low confidence")
            quality_components.append(0.5)
        else:
            quality_components.append(1.0)

        # 3. Structure validation
        has_title = bool(article.title and len(article.title) > 5)
        has_content = bool(article.full_text and len(article.full_text) > 100)
        validation_flags['structure_ok'] = has_title and has_content
        if not validation_flags['structure_ok']:
            quality_issues.append("Missing title or content")
            quality_components.append(0.2)
        else:
            quality_components.append(1.0)

        # 4. Duplicate detection by hash
        duplicate_id = self._check_duplicate_by_hash(db, article.content_hash, str(article.news_id))
        if not duplicate_id:
            # Also check by URL
            duplicate_id = self._check_duplicate_by_url(db, article.url, str(article.news_id))

        validation_flags['is_duplicate'] = bool(duplicate_id)
        if duplicate_id:
            quality_issues.append(f"Duplicate of article {duplicate_id}")
            quality_components.append(0.0)  # Duplicates get 0 score
        else:
            quality_components.append(1.0)

        # 5. Source reliability
        source_reliability = self._get_source_reliability(article.source)
        validation_flags['source_reliable'] = source_reliability > 0.7
        quality_components.append(source_reliability)

        # 6. Overall validity
        validation_flags['is_valid'] = (
            validation_flags['word_count_ok'] and
            validation_flags['language_ok'] and
            validation_flags['structure_ok'] and
            not validation_flags['is_duplicate']
        )

        # Calculate overall quality score (weighted average)
        weights = [0.15, 0.15, 0.20, 0.30, 0.20]  # Sum = 1.0
        quality_score = sum(c * w for c, w in zip(quality_components, weights))

        return {
            'news_id': str(article.news_id),
            'quality_score': quality_score,
            'duplicate_of': duplicate_id,
            'validation_flags': validation_flags,
            'quality_issues': quality_issues,
            'source_reliability_score': source_reliability
        }

    def _process_article_no_commit(self, db: Session, news_id: str) -> DataQualityScore:
        """
        Process article without committing (for batch operations).

        Args:
            db: Database session
            news_id: UUID of article to process

        Returns:
            DataQualityScore object (not yet committed)
        """
        # Validate article
        result = self.validate_article(db, news_id)

        # Check if record exists
        existing = db.query(DataQualityScore).filter(
            DataQualityScore.news_id == result['news_id']
        ).first()

        if existing:
            # Update existing
            existing.quality_score = result['quality_score']
            existing.duplicate_of = result['duplicate_of']
            existing.validation_flags = result['validation_flags']
            existing.quality_issues = result['quality_issues']
            existing.source_reliability_score = result['source_reliability_score']
            existing.created_at = datetime.now(timezone.utc)
            return existing
        else:
            # Create new
            quality_score = DataQualityScore(
                news_id=result['news_id'],
                quality_score=result['quality_score'],
                duplicate_of=result['duplicate_of'],
                validation_flags=result['validation_flags'],
                quality_issues=result['quality_issues'],
                source_reliability_score=result['source_reliability_score'],
                created_at=datetime.now(timezone.utc)
            )
            return quality_score

    def process_article(self, news_id: str) -> DataQualityScore:
        """
        Process article and save quality assessment to database.
        
        DEPRECATED: Use process_batch() for better performance.

        Args:
            news_id: UUID of article to process

        Returns:
            DataQualityScore object
        """
        from src.models.database import get_scoped_session
        
        with get_scoped_session() as db:
            try:
                quality_score = self._process_article_no_commit(db, news_id)
                
                if quality_score not in db:
                    db.add(quality_score)

                logger.info(
                    f"Processed article {news_id}: "
                    f"quality={quality_score.quality_score:.2f}, "
                    f"valid={quality_score.validation_flags.get('is_valid', False)}"
                )

                return quality_score

            except Exception as e:
                logger.error(f"Error processing article {news_id}: {e}")
                raise

    def process_batch(self, limit: int = 100) -> Dict:
        """
        Process batch of unprocessed articles with optimized single transaction.

        Args:
            limit: Maximum number of articles to process

        Returns:
            Statistics dictionary
        """
        from src.models.database import get_scoped_session
        
        with get_scoped_session() as db:
            # Find articles without quality scores (newest first)
            articles = db.query(RawNews).outerjoin(
                DataQualityScore,
                RawNews.news_id == DataQualityScore.news_id
            ).filter(
                DataQualityScore.news_id.is_(None)
            ).order_by(
                RawNews.published_at.desc()
            ).limit(limit).all()

            logger.info(f"Processing {len(articles)} articles for quality assessment")

            stats = {
                'processed': 0,
                'valid': 0,
                'duplicates': 0,
                'low_quality': 0,
                'errors': 0
            }

            processed_items = []

            for article in articles:
                try:
                    quality_score = self._process_article_no_commit(db, str(article.news_id))
                    processed_items.append(quality_score)
                    stats['processed'] += 1

                    if quality_score.validation_flags.get('is_duplicate'):
                        stats['duplicates'] += 1
                    elif quality_score.validation_flags.get('is_valid'):
                        stats['valid'] += 1
                    else:
                        stats['low_quality'] += 1

                except Exception as e:
                    stats['errors'] += 1
                    logger.error(f"Error processing article {article.news_id}: {e}")
                    continue

            # Bulk save all items
            if processed_items:
                db.bulk_save_objects([item for item in processed_items if item not in db])

            logger.info(f"Quality assessment complete. Stats: {stats}")
            return stats

    def get_statistics(self) -> Dict:
        """Get quality statistics."""
        from src.models.database import get_scoped_session
        
        with get_scoped_session() as db:
            total_assessed = db.query(DataQualityScore).count()

            # Count by quality tiers
            high_quality = db.query(DataQualityScore).filter(
                DataQualityScore.quality_score >= 0.8
            ).count()

            medium_quality = db.query(DataQualityScore).filter(
                DataQualityScore.quality_score >= 0.6,
                DataQualityScore.quality_score < 0.8
            ).count()

            low_quality = db.query(DataQualityScore).filter(
                DataQualityScore.quality_score < 0.6
            ).count()

            duplicates = db.query(DataQualityScore).filter(
                DataQualityScore.duplicate_of.isnot(None)
            ).count()

            return {
                'total_assessed': total_assessed,
                'high_quality': high_quality,
                'medium_quality': medium_quality,
                'low_quality': low_quality,
                'duplicates': duplicates,
                'duplicate_rate': duplicates / total_assessed if total_assessed > 0 else 0
            }
