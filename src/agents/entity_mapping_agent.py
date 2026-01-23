"""Agent 3: Entity & Sector Mapping Agent - Extract and map entities."""
import logging
from typing import Dict, List, Optional
from datetime import datetime
from pathlib import Path
from sqlalchemy.orm import Session
import yfinance as yf

from src.models.raw_news import RawNews
from src.models.entities import Entity, NewsEntityMapping
from src.services.llm_service import llm_service

logger = logging.getLogger(__name__)


class EntityMappingAgent:
    """
    Agent 3: Entity & Sector Mapping Agent

    Responsibilities:
    - Named Entity Recognition (companies, people, locations)
    - Ticker symbol mapping
    - Sector classification
    - Exposure type detection (direct/indirect/supply_chain)
    """

    # Common sector mappings
    SECTORS = {
        'Technology': 'TECH',
        'Finance': 'FIN',
        'Healthcare': 'HEALTH',
        'Energy': 'ENERGY',
        'Consumer': 'CONSUMER',
        'Industrial': 'INDUST',
        'Materials': 'MAT',
        'Utilities': 'UTIL',
        'Real Estate': 'REIT',
        'Telecom': 'TELECOM'
    }

    def __init__(self, db: Session):
        """
        Initialize entity mapping agent.

        Args:
            db: Database session
        """
        self.db = db
        self.llm = llm_service

        # Load prompt template
        prompt_path = Path("config/prompts/entity_extraction.txt")
        if prompt_path.exists():
            with open(prompt_path, 'r') as f:
                self.prompt_template = f.read()
        else:
            self.prompt_template = self._get_fallback_prompt()

        # Cache for ticker lookups
        self._ticker_cache = {}

    def _get_fallback_prompt(self) -> str:
        """Fallback prompt if file not found."""
        return """Extract entities from this financial news article:

Title: {title}
Content: {content}

Provide JSON format:
{{
  "entities": [
    {{
      "text": "Apple Inc.",
      "type": "company",
      "ticker": "AAPL",
      "confidence": 0.98,
      "exposure_type": "direct",
      "mention_count": 5
    }}
  ]
}}

Types: company, sector, person, location
Exposure: direct, indirect, supply_chain
Respond ONLY with JSON."""

    def _normalize_ticker(self, company_name: str, suggested_ticker: Optional[str] = None) -> Optional[str]:
        """
        Normalize and validate ticker symbol.

        Args:
            company_name: Company name
            suggested_ticker: LLM-suggested ticker

        Returns:
            Validated ticker or None
        """
        # Check cache
        if company_name in self._ticker_cache:
            return self._ticker_cache[company_name]

        # Try suggested ticker first
        if suggested_ticker:
            try:
                ticker = yf.Ticker(suggested_ticker)
                info = ticker.info
                if info and 'symbol' in info:
                    self._ticker_cache[company_name] = suggested_ticker
                    return suggested_ticker
            except Exception:
                pass

        # Try company name as ticker
        try:
            # Remove common suffixes
            clean_name = company_name.replace(' Inc.', '').replace(' Corp.', '').replace(',', '').strip()

            # Try as ticker
            ticker = yf.Ticker(clean_name)
            info = ticker.info
            if info and 'symbol' in info:
                symbol = info['symbol']
                self._ticker_cache[company_name] = symbol
                return symbol
        except Exception:
            pass

        # Couldn't validate
        logger.warning(f"Could not validate ticker for: {company_name}")
        return None

    def _get_or_create_entity(
        self,
        entity_id: str,
        entity_type: str,
        entity_name: str,
        metadata: Optional[Dict] = None
    ) -> Entity:
        """
        Get existing entity or create new one.

        Args:
            entity_id: Entity ID (ticker or code)
            entity_type: Entity type
            entity_name: Entity name
            metadata: Additional metadata

        Returns:
            Entity object
        """
        entity = self.db.query(Entity).filter(
            Entity.entity_id == entity_id
        ).first()

        if not entity:
            # Create new entity
            entity = Entity(
                entity_id=entity_id,
                entity_type=entity_type,
                entity_name=entity_name,
                metadata=metadata or {},
                created_at=datetime.utcnow()
            )
            self.db.add(entity)
            self.db.commit()
            self.db.refresh(entity)
            logger.info(f"Created new entity: {entity_id} ({entity_name})")

        return entity

    def extract_entities(self, news_id: str) -> Dict:
        """
        Extract entities from article using LLM.

        Args:
            news_id: UUID of article

        Returns:
            Extraction results
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
            content=article.full_text[:3000]  # Limit length
        )

        try:
            # Extract entities with LLM
            logger.info(f"Extracting entities from article {news_id}")
            result = self.llm.generate_json(prompt, temperature=0.1)

            # Validate structure
            if not isinstance(result, dict):
                logger.warning(f"LLM returned non-dict result, using empty entities")
                return {'entities': []}
            
            if 'entities' not in result or not isinstance(result.get('entities'), list):
                logger.warning(f"LLM result missing or invalid 'entities' field")
                return {'entities': []}

            return result

        except ValueError as e:
            # JSON parsing failed - return empty result
            logger.error(f"Error extracting entities from {news_id}: {e}")
            logger.warning(f"Returning empty entity list for article {news_id}")
            return {'entities': []}
        except Exception as e:
            logger.error(f"Error extracting entities from {news_id}: {e}")
            raise

    def process_article(self, news_id: str) -> List[NewsEntityMapping]:
        """
        Process article and create entity mappings.

        Args:
            news_id: UUID of article to process

        Returns:
            List of NewsEntityMapping objects
        """
        try:
            # Extract entities
            extraction = self.extract_entities(news_id)
            entities = extraction.get('entities', [])

            logger.info(f"Extracted {len(entities)} entities from article {news_id}")

            mappings = []

            for ent in entities:
                entity_text = ent.get('text', '')
                entity_type = ent.get('type', 'unknown')
                suggested_ticker = ent.get('ticker')
                confidence = ent.get('confidence', 0.5)
                exposure_type = ent.get('exposure_type', 'direct')
                mention_count = ent.get('mention_count', 1)

                # Handle companies
                if entity_type == 'company':
                    # Validate ticker
                    ticker = self._normalize_ticker(entity_text, suggested_ticker)

                    if ticker:
                        # Create or get entity
                        entity = self._get_or_create_entity(
                            entity_id=ticker,
                            entity_type='company',
                            entity_name=entity_text,
                            metadata={
                                'sector': ent.get('sector'),
                                'industry': ent.get('industry')
                            }
                        )

                        # Create mapping
                        mapping = NewsEntityMapping(
                            news_id=news_id,
                            entity_id=ticker,
                            exposure_type=exposure_type,
                            confidence=confidence,
                            mention_count=mention_count,
                            created_at=datetime.utcnow()
                        )
                        self.db.add(mapping)
                        mappings.append(mapping)

                # Handle sectors
                elif entity_type == 'sector':
                    sector_code = self.SECTORS.get(entity_text, 'OTHER')

                    # Create or get sector entity
                    entity = self._get_or_create_entity(
                        entity_id=sector_code,
                        entity_type='sector',
                        entity_name=entity_text,
                        metadata={}
                    )

                    # Create mapping
                    mapping = NewsEntityMapping(
                        news_id=news_id,
                        entity_id=sector_code,
                        exposure_type='indirect',
                        confidence=confidence,
                        mention_count=mention_count,
                        created_at=datetime.utcnow()
                    )
                    self.db.add(mapping)
                    mappings.append(mapping)

                # Handle people (optional - store as metadata for now)
                elif entity_type == 'person':
                    logger.debug(f"Extracted person: {entity_text} (role: {ent.get('role')})")

            # Commit all mappings
            self.db.commit()

            logger.info(f"Created {len(mappings)} entity mappings for article {news_id}")
            return mappings

        except ValueError as e:
            # JSON parsing or extraction failed - log but don't crash
            self.db.rollback()
            logger.error(f"Error processing entities for {news_id}: {e}")
            logger.warning(f"Skipping entity mapping for article {news_id}")
            return []
        except Exception as e:
            self.db.rollback()
            logger.error(f"Error processing entities for {news_id}: {e}")
            raise

    def process_batch(self, limit: int = 10) -> Dict:
        """
        Process batch of articles without entity mappings.

        Args:
            limit: Maximum number of articles to process

        Returns:
            Statistics dictionary
        """
        # Find processed articles without entity mappings
        from src.models.processed_news import ProcessedNews

        articles = self.db.query(RawNews).join(
            ProcessedNews,
            RawNews.news_id == ProcessedNews.news_id
        ).outerjoin(
            NewsEntityMapping,
            RawNews.news_id == NewsEntityMapping.news_id
        ).filter(
            NewsEntityMapping.mapping_id.is_(None)
        ).limit(limit).all()

        logger.info(f"Processing {len(articles)} articles for entity mapping")

        stats = {
            'processed': 0,
            'total_mappings': 0,
            'companies_found': 0,
            'sectors_found': 0,
            'errors': 0
        }

        for article in articles:
            try:
                mappings = self.process_article(str(article.news_id))
                stats['processed'] += 1
                stats['total_mappings'] += len(mappings)

                # Count by type
                for mapping in mappings:
                    entity = self.db.query(Entity).filter(
                        Entity.entity_id == mapping.entity_id
                    ).first()
                    if entity:
                        if entity.entity_type == 'company':
                            stats['companies_found'] += 1
                        elif entity.entity_type == 'sector':
                            stats['sectors_found'] += 1

            except Exception as e:
                stats['errors'] += 1
                logger.error(f"Error processing article {article.news_id}: {e}")
                continue

        logger.info(f"Entity mapping complete. Stats: {stats}")
        return stats

    def get_statistics(self) -> Dict:
        """Get entity mapping statistics."""
        from sqlalchemy import func

        total_mappings = self.db.query(NewsEntityMapping).count()
        total_entities = self.db.query(Entity).count()

        # Count by entity type
        by_type = self.db.query(
            Entity.entity_type,
            func.count(Entity.entity_id).label('count')
        ).group_by(Entity.entity_type).all()

        # Top entities
        top_entities = self.db.query(
            NewsEntityMapping.entity_id,
            Entity.entity_name,
            func.count(NewsEntityMapping.mapping_id).label('mention_count')
        ).join(
            Entity,
            NewsEntityMapping.entity_id == Entity.entity_id
        ).group_by(
            NewsEntityMapping.entity_id,
            Entity.entity_name
        ).order_by(
            func.count(NewsEntityMapping.mapping_id).desc()
        ).limit(10).all()

        return {
            'total_mappings': total_mappings,
            'total_entities': total_entities,
            'by_type': {et: count for et, count in by_type},
            'top_entities': [
                {'entity_id': eid, 'name': name, 'mentions': count}
                for eid, name, count in top_entities
            ]
        }
