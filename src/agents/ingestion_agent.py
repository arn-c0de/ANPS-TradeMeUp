"""Agent 1: Feed & Data Ingestion Agent - Fetches news from RSS feeds and APIs."""
import hashlib
import logging
from datetime import datetime
from typing import List, Dict, Optional
from dataclasses import dataclass
import feedparser
import requests
from bs4 import BeautifulSoup
from time import sleep
from sqlalchemy.orm import Session
from sqlalchemy.exc import IntegrityError

from src.models.raw_news import RawNews

logger = logging.getLogger(__name__)


@dataclass
class NewsArticle:
    """Data class for a news article."""
    source: str
    title: str
    full_text: str
    url: str
    published_at: datetime
    author: Optional[str] = None
    language: str = "en"
    metadata: Optional[Dict] = None


class IngestionAgent:
    """
    Agent 1: Feed & Data Ingestion Agent

    Responsibilities:
    - Fetch news from RSS feeds
    - Fetch news from APIs
    - Rate limiting and politeness
    - Store raw articles in database
    """

    # RSS Feed sources
    RSS_FEEDS = [
        {
            "name": "Reuters Business",
            "url": "https://www.reutersagency.com/feed/?taxonomy=best-topics&post_type=best",
        },
        {
            "name": "Yahoo Finance",
            "url": "https://finance.yahoo.com/news/rssindex",
        },
        {
            "name": "MarketWatch",
            "url": "http://feeds.marketwatch.com/marketwatch/topstories/",
        },
    ]

    def __init__(self, db: Session, rate_limit_delay: float = 2.0):
        """
        Initialize the ingestion agent.

        Args:
            db: Database session
            rate_limit_delay: Delay between requests in seconds
        """
        self.db = db
        self.rate_limit_delay = rate_limit_delay
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'TradeMeUp/0.1.0 (Educational Research)'
        })

    def _calculate_content_hash(self, text: str) -> str:
        """Calculate SHA-256 hash of content for duplicate detection."""
        return hashlib.sha256(text.encode('utf-8')).hexdigest()

    def _parse_rss_feed(self, feed_url: str, source_name: str) -> List[NewsArticle]:
        """
        Parse RSS feed and extract articles.

        Args:
            feed_url: URL of the RSS feed
            source_name: Name of the news source

        Returns:
            List of NewsArticle objects
        """
        articles = []

        try:
            logger.info(f"Fetching RSS feed: {source_name}")
            feed = feedparser.parse(feed_url)

            for entry in feed.entries:
                try:
                    # Extract title
                    title = entry.get('title', '').strip()
                    if not title:
                        continue

                    # Extract URL
                    url = entry.get('link', '').strip()
                    if not url:
                        continue

                    # Extract published date
                    published_at = None
                    if hasattr(entry, 'published_parsed'):
                        published_at = datetime(*entry.published_parsed[:6])
                    else:
                        published_at = datetime.utcnow()

                    # Extract text (summary or description)
                    full_text = entry.get('summary', entry.get('description', ''))

                    # Clean HTML tags
                    if full_text:
                        soup = BeautifulSoup(full_text, 'html.parser')
                        full_text = soup.get_text().strip()

                    # Extract author
                    author = entry.get('author', None)

                    # Create article object
                    article = NewsArticle(
                        source=source_name,
                        title=title,
                        full_text=full_text if full_text else title,  # Fallback to title
                        url=url,
                        published_at=published_at,
                        author=author,
                        metadata={
                            'tags': entry.get('tags', []),
                            'feed_url': feed_url
                        }
                    )

                    articles.append(article)

                except Exception as e:
                    logger.error(f"Error parsing entry from {source_name}: {e}")
                    continue

            logger.info(f"Extracted {len(articles)} articles from {source_name}")

        except Exception as e:
            logger.error(f"Error fetching RSS feed {source_name}: {e}")

        return articles

    def _save_article(self, article: NewsArticle) -> Optional[str]:
        """
        Save article to database.

        Args:
            article: NewsArticle object

        Returns:
            UUID of saved article or None if duplicate/error
        """
        try:
            # Calculate content hash
            content_hash = self._calculate_content_hash(article.full_text)

            # Create database object
            raw_news = RawNews(
                source=article.source,
                source_url=article.metadata.get('feed_url') if article.metadata else None,
                title=article.title,
                full_text=article.full_text,
                url=article.url,
                published_at=article.published_at,
                fetched_at=datetime.utcnow(),
                content_hash=content_hash,
                author=article.author,
                language=article.language,
                metadata=article.metadata
            )

            # Save to database
            self.db.add(raw_news)
            self.db.commit()
            self.db.refresh(raw_news)

            logger.info(f"Saved article: {raw_news.news_id} - {article.title[:50]}")
            return str(raw_news.news_id)

        except IntegrityError as e:
            self.db.rollback()
            # Duplicate article (URL or content_hash already exists)
            logger.debug(f"Duplicate article detected: {article.url}")
            return None

        except Exception as e:
            self.db.rollback()
            logger.error(f"Error saving article: {e}")
            return None

    def fetch_all_rss_feeds(self) -> Dict[str, int]:
        """
        Fetch news from all configured RSS feeds.

        Returns:
            Dictionary with source names and count of new articles saved
        """
        results = {}

        for feed_config in self.RSS_FEEDS:
            source_name = feed_config['name']
            feed_url = feed_config['url']

            # Fetch articles
            articles = self._parse_rss_feed(feed_url, source_name)

            # Save articles
            saved_count = 0
            for article in articles:
                article_id = self._save_article(article)
                if article_id:
                    saved_count += 1

            results[source_name] = saved_count

            # Rate limiting
            sleep(self.rate_limit_delay)

        logger.info(f"Ingestion complete. Total results: {results}")
        return results

    def fetch_news_api(self, api_key: str, query: str = "stocks OR markets") -> int:
        """
        Fetch news from News API (newsapi.org).

        Args:
            api_key: News API key
            query: Search query

        Returns:
            Number of new articles saved
        """
        if not api_key:
            logger.warning("News API key not provided, skipping")
            return 0

        url = "https://newsapi.org/v2/everything"
        params = {
            'q': query,
            'apiKey': api_key,
            'language': 'en',
            'sortBy': 'publishedAt',
            'pageSize': 50
        }

        try:
            response = self.session.get(url, params=params)
            response.raise_for_status()
            data = response.json()

            articles = []
            for item in data.get('articles', []):
                article = NewsArticle(
                    source=f"NewsAPI: {item.get('source', {}).get('name', 'Unknown')}",
                    title=item.get('title', ''),
                    full_text=item.get('description', '') + "\n\n" + item.get('content', ''),
                    url=item.get('url', ''),
                    published_at=datetime.fromisoformat(
                        item.get('publishedAt', '').replace('Z', '+00:00')
                    ),
                    author=item.get('author'),
                    metadata={'image_url': item.get('urlToImage')}
                )
                articles.append(article)

            # Save articles
            saved_count = 0
            for article in articles:
                article_id = self._save_article(article)
                if article_id:
                    saved_count += 1

            logger.info(f"Saved {saved_count} articles from News API")
            return saved_count

        except Exception as e:
            logger.error(f"Error fetching from News API: {e}")
            return 0

    def process_batch(self, limit: int = 50) -> Dict:
        """Process batch of RSS feeds and save articles."""
        total_saved = 0
        
        for feed_config in self.RSS_FEEDS:
            try:
                articles = self._parse_rss_feed(
                    feed_config['url'],
                    feed_config['name']
                )
                saved = self._save_articles(articles)
                total_saved += saved
                
                if total_saved >= limit:
                    break
                    
                sleep(self.rate_limit_delay)
                
            except Exception as e:
                logger.error(f"Error processing feed {feed_config['name']}: {e}")
                continue
        
        return {
            'success': True,
            'articles_saved': total_saved,
            'feeds_processed': len(self.RSS_FEEDS)
        }

    def get_statistics(self) -> Dict:
        """Get ingestion statistics."""
        total_articles = self.db.query(RawNews).count()

        # Get count by source
        from sqlalchemy import func
        by_source = self.db.query(
            RawNews.source,
            func.count(RawNews.news_id).label('count')
        ).group_by(RawNews.source).all()

        # Get recent articles (last 24 hours)
        from datetime import timedelta
        yesterday = datetime.utcnow() - timedelta(days=1)
        recent_count = self.db.query(RawNews).filter(
            RawNews.fetched_at >= yesterday
        ).count()

        return {
            'total_articles': total_articles,
            'by_source': {source: count for source, count in by_source},
            'last_24_hours': recent_count
        }
