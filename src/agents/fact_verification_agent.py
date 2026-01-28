"""Agent 2.5: Fact Verification Agent - Verify claims and cross-check facts."""
import logging
from typing import Dict, List, Optional
from datetime import datetime, timezone
from sqlalchemy.orm import Session
from sqlalchemy import func

from src.models.processed_news import ProcessedNews
from src.models.analysis import FactVerification
from src.services.llm_service import llm_service

logger = logging.getLogger(__name__)


class FactVerificationAgent:
    """
    Agent 2.5: Fact Verification Agent

    Responsibilities:
    - Verify factual claims in articles
    - Cross-reference with historical data
    - Detect contradictions or inconsistencies
    - Assign credibility scores to claims
    - Flag potential misinformation
    """

    def __init__(self):
        """
        Initialize fact verification agent.
        
        Note: Uses scoped sessions internally for better isolation.
        """
        self.llm = llm_service

    def _verify_article_no_commit(self, db: Session, news_id: str) -> FactVerification:
        """
        Verify facts in an article without committing (for batch operations).

        Args:
            db: Database session
            news_id: UUID of article to verify

        Returns:
            FactVerification object (not yet committed)
        """
        from sqlalchemy.orm import joinedload
        
        # Fetch processed article with news relationship loaded
        article = db.query(ProcessedNews).options(
            joinedload(ProcessedNews.news)
        ).filter(
            ProcessedNews.news_id == news_id
        ).first()

        if not article:
            raise ValueError(f"Processed article {news_id} not found")

        logger.info(f"Verifying facts in article {news_id}")

        # Build verification prompt
        prompt = self._build_verification_prompt(article)

        try:
            # Get LLM verification
            result = self.llm.generate_json(prompt, temperature=0.1)

            # Extract verification results
            claims_verified = result.get('claims_verified', [])
            contradictions = result.get('contradictions', [])
            credibility_score = result.get('overall_credibility', 0.75)
            verification_notes = result.get('notes', '')

            # Create verification record
            verification = FactVerification(
                news_id=news_id,
                claims_verified=claims_verified,
                contradictions_found=len(contradictions) > 0,
                contradiction_details=contradictions,
                credibility_score=credibility_score,
                verification_method='llm_cross_check',
                verified_at=datetime.now(timezone.utc),
                verification_notes=verification_notes
            )

            logger.info(
                f"Verified {len(claims_verified)} claims in article {news_id}. "
                f"Credibility: {credibility_score:.2f}"
            )

            return verification

        except Exception as e:
            logger.error(f"Error verifying article {news_id}: {e}")
            # Create fallback verification with default values
            verification = FactVerification(
                news_id=news_id,
                claims_verified=[],
                contradictions_found=False,
                contradiction_details=[],
                credibility_score=0.7,  # Neutral default
                verification_method='fallback',
                verified_at=datetime.now(timezone.utc),
                verification_notes=f"Verification failed: {str(e)}"
            )
            return verification

    def verify_article(self, news_id: str) -> FactVerification:
        """
        Verify facts in an article.
        
        DEPRECATED: Use process_batch() for better performance.

        Args:
            news_id: UUID of article to verify

        Returns:
            FactVerification object
        """
        from src.models.database import get_scoped_session
        
        with get_scoped_session() as db:
            verification = self._verify_article_no_commit(db, news_id)
            db.add(verification)
            return verification

    def _build_verification_prompt(self, article: ProcessedNews) -> str:
        """Build fact verification prompt."""
        facts_text = "\n".join([
            f"- {f.get('fact', '') if isinstance(f, dict) else str(f)}"
            for f in (article.key_facts or [])[:10]
        ])
        
        # Get title from news relationship (correct name in model)
        article_title = 'N/A'
        if hasattr(article, 'news') and article.news:
            article_title = article.news.title

        prompt = f"""Verify the factual accuracy of claims in this financial news article:

Article Title: {article_title}"

Key Facts Claimed:
{facts_text}

Event Type: {article.event_type}
Sentiment: {article.sentiment}

Please analyze and verify these facts. Provide your response in JSON format:

{{
  "claims_verified": [
    {{
      "claim": "Specific claim from article",
      "verdict": "verified|unverifiable|false",
      "confidence": 0.95,
      "reasoning": "Why this verdict was reached"
    }}
  ],
  "contradictions": [
    {{
      "claim_1": "First contradictory statement",
      "claim_2": "Second contradictory statement",
      "severity": "high|medium|low"
    }}
  ],
  "overall_credibility": 0.85,
  "notes": "Summary of verification findings"
}}

Verification Criteria:
1. Internal consistency - Do claims contradict each other?
2. Plausibility - Are claims realistic given market context?
3. Specificity - Are claims specific or vague?
4. Source reliability - Consider the news source

Respond ONLY with JSON."""

        return prompt

    def process_batch(self, limit: int = 10) -> Dict:
        """
        Process batch of articles for fact verification with optimized single transaction.

        Args:
            limit: Maximum number of articles to process

        Returns:
            Statistics dictionary
        """
        from src.models.database import get_scoped_session
        
        with get_scoped_session() as db:
            # Find processed articles without verification
            articles = db.query(ProcessedNews).outerjoin(
                FactVerification,
                ProcessedNews.news_id == FactVerification.news_id
            ).filter(
                FactVerification.verification_id.is_(None)
            ).order_by(
                ProcessedNews.processing_timestamp.desc()
            ).limit(limit).all()

            logger.info(f"Verifying {len(articles)} articles")

            stats = {
                'processed': 0,
                'high_credibility': 0,  # > 0.8
                'medium_credibility': 0,  # 0.6 - 0.8
                'low_credibility': 0,  # < 0.6
                'contradictions_found': 0,
                'errors': 0
            }

            verifications = []

            for article in articles:
                try:
                    verification = self._verify_article_no_commit(db, str(article.news_id))
                    verifications.append(verification)
                    stats['processed'] += 1

                    # Categorize by credibility
                    if verification.credibility_score >= 0.8:
                        stats['high_credibility'] += 1
                    elif verification.credibility_score >= 0.6:
                        stats['medium_credibility'] += 1
                    else:
                        stats['low_credibility'] += 1

                    if verification.contradictions_found:
                        stats['contradictions_found'] += 1

                except Exception as e:
                    stats['errors'] += 1
                    logger.error(f"Error verifying article {article.news_id}: {e}")
                    continue

            # Bulk save all verifications
            if verifications:
                db.bulk_save_objects(verifications)

            logger.info(f"Fact verification complete. Stats: {stats}")
            return stats

    def get_statistics(self) -> Dict:
        """Get fact verification statistics."""
        from src.models.database import get_scoped_session
        
        with get_scoped_session() as db:
            total_verified = db.query(FactVerification).count()

            if total_verified == 0:
                return {
                    'total_verified': 0,
                    'avg_credibility': 0.0,
                    'contradictions_found': 0,
                    'high_credibility_pct': 0.0
                }

            # Average credibility
            avg_cred = db.query(
                func.avg(FactVerification.credibility_score)
            ).scalar() or 0.0

            # Contradictions count
            contradictions = db.query(FactVerification).filter(
                FactVerification.contradictions_found == True
            ).count()

            # High credibility percentage
            high_cred = db.query(FactVerification).filter(
                FactVerification.credibility_score >= 0.8
            ).count()

            return {
                'total_verified': total_verified,
                'avg_credibility': float(avg_cred),
                'contradictions_found': contradictions,
                'high_credibility_pct': (high_cred / total_verified * 100) if total_verified > 0 else 0.0,
                'by_method': self._get_method_breakdown(db)
            }

    def _get_method_breakdown(self, db: Session) -> Dict:
        """Get breakdown by verification method."""
        methods = db.query(
            FactVerification.verification_method,
            func.count(FactVerification.verification_id).label('count')
        ).group_by(FactVerification.verification_method).all()

        return {method: count for method, count in methods}
