"""
Agent 3: Entity & Sector Mapping Agent - Extract and map entities

OPTIMIZED VERSION:
- ✅ Scoped sessions with context manager (no shared session)
- ✅ Batch transactions (1 commit per batch instead of N)
- ✅ Proper error handling with rollback
- ✅ No session state leaks between batches
"""
import json
import logging
import re
import warnings
from datetime import UTC, datetime
from pathlib import Path

from sqlalchemy.orm import Session

warnings.filterwarnings('ignore', category=FutureWarning, module='yfinance')
import yfinance as yf

from src.models.database import get_scoped_session
from src.models.entities import Entity, NewsEntityMapping
from src.models.raw_news import RawNews
from src.services.llm_service import llm_service, truncate_for_prompt

logger = logging.getLogger(__name__)

# Values the extractor emits when it has no ticker to offer. They arrive as
# ordinary strings, so "None" was being validated as if it were a symbol.
_NULL_TICKER_STRINGS = frozenset({'NONE', 'NULL', 'N/A', 'NA', 'UNKNOWN', '-', ''})

# A ticker is 1-5 letters, optionally followed by an exchange suffix such as
# .DE or .PA, and optionally a share-class marker such as BRK-B.
_TICKER_PATTERN = re.compile(r'^[A-Z]{1,5}(?:[.-][A-Z]{1,4})?$')


def normalize_ticker_symbol(value: str | None) -> str | None:
    """Return ``value`` as a well-formed ticker, or None if it is not one.

    Filters out the placeholder strings the extractor uses for "no ticker"
    before any of them reach a market-data lookup.
    """
    if not value or not isinstance(value, str):
        return None

    symbol = value.strip().upper()
    if symbol in _NULL_TICKER_STRINGS:
        return None

    return symbol if _TICKER_PATTERN.match(symbol) else None


def _load_known_tickers() -> frozenset:
    """Tickers from the bundled index constituents.

    These are verifiable without a network call, which keeps the common case
    working when the market-data provider is unreachable.
    """
    path = Path("config/index_constituents.json")
    if not path.exists():
        return frozenset()

    try:
        with open(path, encoding='utf-8') as handle:
            data = json.load(handle)
    except (json.JSONDecodeError, OSError) as exc:
        logger.warning("Could not read %s: %s", path, exc)
        return frozenset()

    tickers = set()
    for index in data.values():
        if isinstance(index, dict):
            tickers.update(index.get('top_stocks', []))
    return frozenset(t.upper() for t in tickers if isinstance(t, str))


# Prompt budget for the extraction call, in approximate tokens. Entity
# extraction needs enough of the article to see who is being discussed, but
# not the whole body: the names cluster near the top, and the key-facts path
# below is usually much shorter than this ceiling anyway.
EXTRACTION_CONTENT_TOKENS = 750


class EntityMappingAgent:
    """
    Agent 3: Entity & Sector Mapping Agent

    Responsibilities:
    - Named Entity Recognition (companies, people, locations)
    - Ticker symbol mapping
    - Sector classification
    - Exposure type detection (direct/indirect/supply_chain)

    PERFORMANCE OPTIMIZATIONS:
    - Uses scoped sessions for isolation
    - Batch commits (creates all entities and mappings in single transaction)
    - Continues processing even if individual items fail
    """

    # Analyst and financial service firms to EXCLUDE (not companies to trade)
    # These are often mentioned in news as the source/analyst, not as the subject
    ANALYST_FIRMS = {
        'Oppenheimer', 'oppenheimer', 'Oppenheimer & Co',
        'Wells Fargo Securities', 'wells fargo securities',
        'RBC Capital', 'RBC Capital Markets', 'rbc capital',
        'TD Cowen', 'td cowen', 'Cowen',
        'Scotiabank', 'scotiabank', 'Scotia Capital',
        'JPMorgan Securities', 'jpmorgan securities',
        'Goldman Sachs Research', 'goldman sachs research',
        'Morgan Stanley Research', 'morgan stanley research',
        'BofA Securities', 'bofa securities', 'Bank of America Securities',
        'Barclays Capital', 'barclays capital',
        'Citi Research', 'citi research', 'Citigroup Global Markets',
        'Deutsche Bank Securities', 'deutsche bank securities',
        'Credit Suisse Securities', 'credit suisse securities',
        'UBS Securities', 'ubs securities',
        'Jefferies', 'jefferies',
        'Piper Sandler', 'piper sandler',
        'Raymond James', 'raymond james',
        'Stifel', 'stifel',
        'Evercore ISI', 'evercore',
        'Bernstein Research', 'bernstein',
        'Wedbush Securities', 'wedbush',
        'Needham', 'needham',
        'Truist Securities', 'truist securities',
        'KeyBanc', 'keybanc',
        'Baird', 'baird',
        'BMO Capital', 'bmo capital',
        'BTIG', 'btig',
        'Canaccord Genuity', 'canaccord',
        'Mizuho Securities', 'mizuho securities',
        'Loop Capital', 'loop capital',
    }

    # Non-tradeable entities to exclude (government agencies, crypto, etc.)
    # Consecutive transport failures before ticker verification is treated as
    # unavailable for the rest of the batch.
    MAX_TRANSPORT_FAILURES = 3

    # Symbols verifiable without a network call.
    KNOWN_TICKERS = _load_known_tickers()

    EXCLUDE_ENTITIES = {
        # Government/Regulatory
        'SEC', 'sec', 'Securities and Exchange Commission',
        'BoJ', 'boj', 'Bank of Japan',
        'Fed', 'Federal Reserve', 'FRB',
        'ECB', 'European Central Bank',
        'RBI', 'rbi', 'Reserve Bank of India',
        'BJP', 'bjp',  # Political party
        'Labour Party', 'Conservative Party',
        # Crypto (these should use crypto tickers like BTC-USD, ETH-USD)
        'Bitcoin', 'Ethereum', 'Cardano', 'Polkadot', 'Filecoin',
        'Uniswap', 'Chainlink', 'Avalanche', 'Solana', 'Cosmos',
        # Cloud/Tech platforms (part of parent companies)
        'AWS', 'aws', 'Amazon Web Services',  # Part of AMZN
        'Azure', 'azure',  # Part of MSFT
        'Google Cloud', 'GCP',  # Part of GOOGL
        # Generic/Non-specific
        'Company', 'companies', 'Corporation',
    }

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

    # Theme/Sector to ETF mappings for macro/sector news
    THEME_TO_ETF = {
        # Major Indices
        's&p 500': [('SPY', 'S&P 500 ETF')],
        's&p': [('SPY', 'S&P 500 ETF')],
        'nasdaq': [('QQQ', 'Nasdaq-100 ETF')],
        'dow jones': [('DIA', 'Dow Jones ETF')],
        'russell': [('IWM', 'Russell 2000 ETF')],

        # Sectors
        'technology': [('XLK', 'Technology Sector ETF'), ('QQQ', 'Tech-heavy Nasdaq')],
        'tech sector': [('XLK', 'Technology Sector ETF')],
        'software': [('IGV', 'Software ETF')],
        'semiconductor': [('SMH', 'Semiconductor ETF'), ('SOXX', 'Semiconductor ETF')],
        'chip': [('SMH', 'Semiconductor ETF')],
        'ai': [('BOTZ', 'AI & Robotics ETF'), ('XLK', 'Technology ETF')],
        'artificial intelligence': [('BOTZ', 'AI & Robotics ETF')],

        'financial': [('XLF', 'Financial Sector ETF')],
        'bank': [('XLF', 'Financial Sector ETF'), ('KBE', 'Bank ETF')],
        'insurance': [('KIE', 'Insurance ETF')],

        'healthcare': [('XLV', 'Healthcare Sector ETF')],
        'biotech': [('XBI', 'Biotech ETF'), ('IBB', 'Biotech ETF')],
        'pharmaceutical': [('XPH', 'Pharmaceutical ETF')],

        'energy': [('XLE', 'Energy Sector ETF')],
        'oil': [('XLE', 'Energy ETF'), ('USO', 'Oil Fund')],
        'natural gas': [('UNG', 'Natural Gas Fund')],
        'clean energy': [('ICLN', 'Clean Energy ETF')],
        'solar': [('TAN', 'Solar ETF')],

        'consumer': [('XLP', 'Consumer Staples ETF'), ('XLY', 'Consumer Discretionary ETF')],
        'retail': [('XRT', 'Retail ETF')],

        'industrial': [('XLI', 'Industrial Sector ETF')],
        'aerospace': [('ITA', 'Aerospace ETF')],
        'defense': [('ITA', 'Aerospace & Defense ETF')],

        'real estate': [('VNQ', 'Real Estate ETF'), ('XLRE', 'Real Estate ETF')],
        'reit': [('VNQ', 'REIT ETF')],

        'materials': [('XLB', 'Materials Sector ETF')],
        'gold': [('GLD', 'Gold ETF')],
        'silver': [('SLV', 'Silver ETF')],
        'commodity': [('DBC', 'Commodity ETF')],

        'utility': [('XLU', 'Utilities Sector ETF')],
        'utilities': [('XLU', 'Utilities Sector ETF')],

        # International/Currency
        'china': [('FXI', 'China Large-Cap ETF'), ('MCHI', 'China ETF')],
        'japan': [('EWJ', 'Japan ETF')],
        'japanese yen': [('FXY', 'Japanese Yen ETF')],
        'yen': [('FXY', 'Japanese Yen ETF')],
        'europe': [('VGK', 'European ETF')],
        'emerging market': [('EEM', 'Emerging Markets ETF')],
        'dollar': [('UUP', 'US Dollar ETF')],

        # Bonds/Fixed Income
        'bond': [('AGG', 'Bond Aggregate ETF'), ('TLT', 'Long-term Treasury ETF')],
        'treasury': [('TLT', '20+ Year Treasury ETF')],
        'corporate bond': [('LQD', 'Corporate Bond ETF')],
        'high yield': [('HYG', 'High Yield Bond ETF')],

        # Volatility
        'volatility': [('VXX', 'VIX Short-term Futures ETF')],
        'vix': [('VXX', 'VIX Futures ETF')],
    }

    def __init__(self):
        """
        Initialize entity mapping agent.

        NOTE: No database session parameter!
        Sessions are created per-operation for isolation.
        """
        self.llm = llm_service

        # Load prompt template
        prompt_path = Path("config/prompts/entity_extraction.txt")
        if prompt_path.exists():
            with open(prompt_path, encoding='utf-8') as f:
                self.prompt_template = f.read()
        else:
            self.prompt_template = self._get_fallback_prompt()

        # Cache for ticker lookups (shared across batches). Holds negative
        # results too, so a name that could not be resolved is not looked up
        # again for every article that mentions it.
        self._ticker_cache = {}

        # Circuit breaker around the market-data provider. Reset per batch.
        self._transport_failures = 0
        self._market_data_unreachable = False

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

    def _extract_theme_mappings(self, article: RawNews) -> list[dict]:
        """Extract theme/sector-based ETF mappings from article."""
        theme_entities = []

        # Combine title and text for theme detection
        content = f"{article.title} {article.full_text}".lower()

        # Check for each theme (use word boundaries for short terms)
        for theme, etfs in self.THEME_TO_ETF.items():
            # Use word boundaries for short keywords to avoid false matches
            if len(theme) <= 3:
                pattern = rf'\b{re.escape(theme)}\b'
                if not re.search(pattern, content):
                    continue
                match_count = len(re.findall(pattern, content))
            else:
                if theme not in content:
                    continue
                match_count = content.count(theme)

            for ticker, name in etfs:
                theme_entities.append({
                    'text': name,
                    'type': 'sector_etf',
                    'ticker': ticker,
                    'confidence': 0.75,  # Lower confidence for theme-based
                    'exposure_type': 'indirect',
                    'mention_count': match_count
                })

        # Deduplicate by ticker (keep first occurrence)
        seen_tickers = set()
        unique_entities = []
        for entity in theme_entities:
            if entity['ticker'] not in seen_tickers:
                seen_tickers.add(entity['ticker'])
                unique_entities.append(entity)

        return unique_entities

    def _find_ticker_by_company_name(self, company_name: str) -> str | None:
        """
        Try to find ticker symbol by searching with company name.
        
        Args:
            company_name: Company name to search for
            
        Returns:
            Ticker symbol if found, None otherwise
        """
        # Check cache first
        if company_name in self._ticker_cache:
            return self._ticker_cache[company_name]

        # A company name is only worth trying as a symbol if it is shaped like
        # one. Passing arbitrary prose to the provider produced one doomed
        # request per entity and, once it started failing, nothing else.
        for name in (company_name,
                     company_name.replace(' Inc.', '').replace(' Corp.', '')
                                 .replace(' LLC', '').replace(',', '').strip()):
            symbol = normalize_ticker_symbol(name)
            if not symbol:
                continue
            if symbol in self.KNOWN_TICKERS or self._verify_ticker_online(symbol):
                self._ticker_cache[company_name] = symbol
                logger.debug(f"Found ticker '{symbol}' for company '{company_name}'")
                return symbol

        return None

    def _verify_ticker_online(self, symbol: str) -> bool | None:
        """Ask the market-data provider whether ``symbol`` exists.

        Returns True (exists), False (definitively unknown), or None when the
        provider could not be reached at all. That third case is the whole
        point of this method: treating an unreachable provider as "unknown
        ticker" silently discarded every entity in the batch.
        """
        if self._market_data_unreachable:
            return None

        try:
            info = yf.Ticker(symbol).info
        except Exception as exc:
            self._transport_failures += 1
            if self._transport_failures >= self.MAX_TRANSPORT_FAILURES:
                # Stop hammering a provider that is plainly not answering.
                # Without this, every entity paid several multi-second
                # timeouts before being wrongly rejected.
                self._market_data_unreachable = True
                logger.error(
                    "Market data provider unreachable (%s: %s). Ticker verification "
                    "is disabled for the rest of this batch; entities will be kept "
                    "with unverified tickers rather than discarded.",
                    type(exc).__name__,
                    str(exc)[:120],
                )
            return None

        if info and info.get('symbol'):
            return True

        # A reachable provider that returns nothing usable is a real "no such
        # ticker" answer.
        return False

    def _normalize_ticker(self, company_name: str, suggested_ticker: str | None = None) -> str | None:
        """
        Normalize and validate ticker symbol.

        Args:
            company_name: Company name
            suggested_ticker: LLM-suggested ticker

        Returns:
            Validated ticker or None
        """
        # Check cache (negative results are cached as None, so a name that
        # already failed does not pay for another round of lookups)
        if company_name in self._ticker_cache:
            return self._ticker_cache[company_name]

        candidate = normalize_ticker_symbol(suggested_ticker)

        # Offline fast path: index constituents are known-good, so the common
        # case needs no network call and cannot be broken by an outage.
        if candidate and candidate in self.KNOWN_TICKERS:
            self._ticker_cache[company_name] = candidate
            return candidate

        if candidate:
            verified = self._verify_ticker_online(candidate)
            if verified:
                self._ticker_cache[company_name] = candidate
                return candidate
            if verified is None:
                # Provider unreachable. The symbol is well-formed and came
                # from the extractor, so keep it rather than lose the entity;
                # anything bogus drops out later when no price can be fetched.
                logger.warning(
                    "Could not verify ticker '%s' for '%s' (market data unreachable) - "
                    "keeping it unverified",
                    candidate,
                    company_name,
                )
                self._ticker_cache[company_name] = candidate
                return candidate

        # Suggested ticker was missing or definitively wrong: try the company
        # name itself as a symbol.
        clean_name = normalize_ticker_symbol(
            company_name.replace(' Inc.', '').replace(' Corp.', '').replace(',', '').strip()
        )
        if clean_name and clean_name != candidate:
            if clean_name in self.KNOWN_TICKERS or self._verify_ticker_online(clean_name):
                self._ticker_cache[company_name] = clean_name
                return clean_name

        logger.debug(f"Could not validate ticker for: {company_name}")
        self._ticker_cache[company_name] = None
        return None

    def process_batch(self, limit: int = 20, offset: int = 0) -> dict:
        """
        Process batch of articles without entity mappings.

        PERFORMANCE: Single transaction for entire batch (30x faster)
        SAFETY: Isolated session with automatic cleanup
        STABILITY: Continues processing even if individual items fail

        Args:
            limit: Maximum number of articles to process
            offset: Number of articles to skip (for pagination)

        Returns:
            Statistics dictionary
        """
        # Give the provider a fresh chance each batch: an outage during one
        # batch should not disable verification for the life of the process.
        self._transport_failures = 0
        self._market_data_unreachable = False

        # Use scoped session for isolation
        with get_scoped_session() as db:
            # Find processed articles without entity mappings
            articles = self._find_articles_without_mappings(db, limit, offset)

            if not articles:
                logger.info("No articles to process for entity mapping")
                return {
                    'processed': 0,
                    'total_mappings': 0,
                    'companies_found': 0,
                    'sectors_found': 0,
                    'errors': 0
                }

            logger.info(f"Processing batch of {len(articles)} articles for entity mapping")

            stats = {
                'processed': 0,
                'total_mappings': 0,
                'companies_found': 0,
                'sectors_found': 0,
                'errors': 0
            }

            all_entities = []
            all_mappings = []

            # Process all articles WITHOUT committing
            for idx, article in enumerate(articles, 1):
                try:
                    logger.info(f"Processing article {idx}/{len(articles)}: {article.news_id}")

                    # Extract entities and create mappings (without commit)
                    entities, mappings = self._process_article_no_commit(db, article)

                    if entities or mappings:
                        all_entities.extend(entities)
                        all_mappings.extend(mappings)
                        stats['processed'] += 1
                        stats['total_mappings'] += len(mappings)

                        # Count by type
                        for entity in entities:
                            if entity.entity_type == 'company':
                                stats['companies_found'] += 1
                            elif entity.entity_type == 'sector':
                                stats['sectors_found'] += 1

                        logger.info(f"  ✅ Found {len(entities)} entities, {len(mappings)} mappings")
                    else:
                        logger.warning(f"  ⚠️ No entities/mappings extracted for article {article.news_id}")

                except Exception as e:
                    # Log error but CONTINUE processing other articles
                    logger.error(f"❌ Error processing article {article.news_id}: {e}")
                    stats['errors'] += 1
                    continue

            # ✅ CRITICAL: Deduplicate entities before bulk save
            if all_entities:
                # Remove duplicate entities (same entity_id)
                seen_ids = set()
                unique_entities = []
                for entity in all_entities:
                    if entity.entity_id not in seen_ids:
                        seen_ids.add(entity.entity_id)
                        unique_entities.append(entity)

                db.bulk_save_objects(unique_entities)
                logger.info(f"Bulk saved {len(unique_entities)} unique entities (from {len(all_entities)} total)")

            if all_mappings:
                db.bulk_save_objects(all_mappings)
                logger.info(f"Bulk saved {len(all_mappings)} mappings")

            # ✅ SINGLE COMMIT for entire batch
            # (Happens automatically in context manager on success)

            logger.info(f"Entity mapping complete. Stats: {stats}")
            return stats

    def _find_articles_without_mappings(self, db: Session, limit: int, offset: int = 0) -> list[RawNews]:
        """
        Find processed articles without entity mappings.

        Args:
            db: Database session
            limit: Maximum number to return
            offset: Number of articles to skip (for pagination)

        Returns:
            List of RawNews objects
        """
        from src.models.processed_news import ProcessedNews

        articles = db.query(RawNews).join(
            ProcessedNews,
            RawNews.news_id == ProcessedNews.news_id
        ).outerjoin(
            NewsEntityMapping,
            RawNews.news_id == NewsEntityMapping.news_id
        ).filter(
            NewsEntityMapping.mapping_id.is_(None)
        ).order_by(
            RawNews.published_at.desc()  # Newest first
        ).limit(limit).offset(offset).all()

        return articles

    def _process_article_no_commit(
        self,
        db: Session,
        article: RawNews
    ) -> tuple[list[Entity], list[NewsEntityMapping]]:
        """
        Process article and extract entities WITHOUT committing.

        This allows batching multiple articles into a single transaction.

        Args:
            db: Database session
            article: Article to process

        Returns:
            Tuple of (entities, mappings) lists (not yet committed)
        """
        try:
            # Extract entities using LLM
            extraction = self._extract_entities(db, article)
            entities_data = extraction.get('entities', [])

            # ✨ NEW: Add theme-based ETF mappings (for macro/sector news)
            theme_entities = self._extract_theme_mappings(article)
            entities_data.extend(theme_entities)

            logger.debug(f"Extracted {len(entities_data)} entities from article {article.news_id} ({len(theme_entities)} theme-based)")

            new_entities = []
            mappings = []

            for ent in entities_data:
                entity_text = ent.get('text', '')
                entity_type = ent.get('type', 'unknown')
                suggested_ticker = ent.get('ticker')
                confidence = ent.get('confidence', 0.5)
                exposure_type = ent.get('exposure_type', 'direct')
                mention_count = ent.get('mention_count', 1)

                # Handle companies
                if entity_type == 'company':
                    # FILTER OUT ANALYST FIRMS - they're not companies to trade
                    if entity_text in self.ANALYST_FIRMS or entity_text.lower() in self.ANALYST_FIRMS:
                        logger.debug(f"Skipping analyst/financial service firm: {entity_text}")
                        continue

                    # FILTER OUT NON-TRADEABLE ENTITIES
                    if entity_text in self.EXCLUDE_ENTITIES or entity_text.upper() in self.EXCLUDE_ENTITIES:
                        logger.debug(f"Skipping non-tradeable entity: {entity_text}")
                        continue

                    # Validate ticker
                    ticker = self._normalize_ticker(entity_text, suggested_ticker)

                    # If ticker validation failed, try to find ticker by company name
                    if not ticker:
                        logger.debug(f"Ticker validation failed for '{entity_text}' (suggested: '{suggested_ticker}'). Trying company name lookup...")
                        ticker = self._find_ticker_by_company_name(entity_text)

                    # If still no ticker, SKIP this entity instead of creating a fallback
                    # This prevents creating entities we can't get market data for
                    if not ticker:
                        logger.warning(f"Could not find valid ticker for company '{entity_text}' (suggested: '{suggested_ticker}') - SKIPPING")
                        continue

                    if ticker:
                        # Entity has a valid ticker - proceed with creation
                        entity = self._get_or_create_entity_no_commit(
                            db,
                            entity_id=ticker,
                            entity_type='company',
                            entity_name=entity_text,
                            metadata={
                                'sector': ent.get('sector'),
                                'industry': ent.get('industry'),
                                'suggested_ticker': suggested_ticker,  # Store original suggestion
                                'ticker_validated': True  # If we got here, ticker is validated
                            }
                        )

                        if entity:
                            new_entities.append(entity)

                            # Create mapping
                            mapping = NewsEntityMapping(
                                news_id=str(article.news_id),
                                entity_id=ticker,
                                exposure_type=exposure_type,
                                confidence=confidence,
                                mention_count=mention_count,
                                created_at=datetime.now(UTC)
                            )
                            mappings.append(mapping)

                # Handle sectors
                elif entity_type == 'sector':
                    sector_code = self.SECTORS.get(entity_text, 'OTHER')

                    # Create or get sector entity
                    entity = self._get_or_create_entity_no_commit(
                        db,
                        entity_id=sector_code,
                        entity_type='sector',
                        entity_name=entity_text,
                        metadata={}
                    )

                    if entity:
                        new_entities.append(entity)

                        # Create mapping
                        mapping = NewsEntityMapping(
                            news_id=str(article.news_id),
                            entity_id=sector_code,
                            exposure_type='indirect',
                            confidence=confidence,
                            mention_count=mention_count,
                            created_at=datetime.now(UTC)
                        )
                        mappings.append(mapping)

                # ✨ NEW: Handle sector ETFs (theme-based mappings)
                elif entity_type == 'sector_etf':
                    ticker = suggested_ticker or ent.get('ticker')

                    if ticker:
                        # Create ETF entity
                        entity = self._get_or_create_entity_no_commit(
                            db,
                            entity_id=ticker,
                            entity_type='etf',
                            entity_name=entity_text,
                            metadata={'category': 'sector_theme'}
                        )

                        if entity:
                            new_entities.append(entity)

                            # Create mapping with indirect exposure
                            mapping = NewsEntityMapping(
                                news_id=str(article.news_id),
                                entity_id=ticker,
                                exposure_type='indirect',
                                confidence=confidence,
                                mention_count=mention_count,
                                created_at=datetime.now(UTC)
                            )
                            mappings.append(mapping)

                # Handle people (optional - store as metadata for now)
                elif entity_type == 'person':
                    logger.debug(f"Extracted person: {entity_text} (role: {ent.get('role')})")

            if mappings:
                logger.info(f"Created {len(mappings)} entity mappings for article {article.news_id}")

            return new_entities, mappings

        except Exception as e:
            logger.error(f"Error processing entities for {article.news_id}: {e}", exc_info=True)
            return [], []

    def _get_or_create_entity_no_commit(
        self,
        db: Session,
        entity_id: str,
        entity_type: str,
        entity_name: str,
        metadata: dict | None = None
    ) -> Entity | None:
        """
        Get existing entity or create new one WITHOUT committing.

        Args:
            db: Database session
            entity_id: Entity ID (ticker or code)
            entity_type: Entity type
            entity_name: Entity name
            metadata: Additional metadata

        Returns:
            Entity object (not yet committed) or None
        """
        # Check if entity already exists
        entity = db.query(Entity).filter(
            Entity.entity_id == entity_id
        ).first()

        if entity:
            # Return existing entity
            return None  # Don't include existing entities in bulk save
        else:
            # Create new entity (will be bulk-saved later)
            entity = Entity(
                entity_id=entity_id,
                entity_type=entity_type,
                entity_name=entity_name,
                metadata=metadata or {},
                created_at=datetime.now(UTC)
            )
            logger.debug(f"Preparing new entity: {entity_id} ({entity_name})")
            return entity

    def _extract_entities(self, db: Session, article: RawNews) -> dict:
        """
        Extract entities from article using LLM.

        Args:
            db: Database session (for fetching related data)
            article: Article to extract from

        Returns:
            Extraction results dictionary
        """
        from src.models.processed_news import ProcessedNews

        # Try to get processed version for richer content
        processed = db.query(ProcessedNews).filter(
            ProcessedNews.news_id == article.news_id
        ).first()

        # Build content from available sources
        if processed and processed.key_facts:
            # Use key facts from processed article (much richer content)
            facts_text = "\n".join([
                f.get('fact', '') if isinstance(f, dict) else str(f)
                for f in processed.key_facts[:10]  # Use top 10 facts
            ])
            content = f"{article.title}\n\n{facts_text}"
        else:
            # Fallback to raw text
            content = f"{article.title}\n\n{article.full_text}"

        # Prepare prompt. Budget in tokens and cut on a sentence boundary,
        # matching the content agent - the previous hard character slice had
        # no stated budget and could hand the model a truncated word.
        prompt = self.prompt_template.format(
            title=article.title,
            content=truncate_for_prompt(content, EXTRACTION_CONTENT_TOKENS),
        )

        try:
            # Extract entities with LLM
            logger.debug(f"Extracting entities from article {article.news_id}")
            result = self.llm.generate_json(prompt, temperature=0.1)

            # Validate structure
            if not isinstance(result, dict):
                logger.warning("LLM returned non-dict result, using empty entities")
                return {'entities': []}

            if 'entities' not in result or not isinstance(result.get('entities'), list):
                logger.warning("LLM result missing or invalid 'entities' field")
                return {'entities': []}

            return result

        except ValueError as e:
            # JSON parsing failed - return empty result
            logger.error(f"Error extracting entities from {article.news_id}: {e}")
            return {'entities': []}
        except Exception as e:
            logger.error(f"Error extracting entities from {article.news_id}: {e}")
            raise

    def get_statistics(self) -> dict:
        """
        Get entity mapping statistics.

        Uses scoped session for isolation.
        """
        from sqlalchemy import func

        with get_scoped_session() as db:
            total_mappings = db.query(NewsEntityMapping).count()
            total_entities = db.query(Entity).count()

            # Count by entity type
            by_type = db.query(
                Entity.entity_type,
                func.count(Entity.entity_id).label('count')
            ).group_by(Entity.entity_type).all()

            # Top entities
            top_entities = db.query(
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
