"""
Live Market Data Provider
Fetches real-time stock market data from various sources
"""
import os
import warnings

warnings.filterwarnings('ignore', category=FutureWarning, module='yfinance')
warnings.filterwarnings('ignore', category=DeprecationWarning, module='yfinance')
warnings.filterwarnings('ignore', message='.*Timestamp.utcnow.*')
try:
    from pandas.errors import Pandas4Warning
    warnings.filterwarnings('ignore', category=Pandas4Warning)
except ImportError:
    pass
# Suppress yfinance's own logging
import logging as yf_logging

yf_logging.getLogger('yfinance').setLevel(yf_logging.ERROR)

import logging
import threading
import time
from datetime import datetime

import pandas as pd
import yfinance as yf

logger = logging.getLogger(__name__)

# Historical bars change at most once per trading day, but an unbounded cache
# would pin a stale snapshot for the whole process lifetime.
HISTORICAL_CACHE_TTL = 300  # seconds
HISTORICAL_CACHE_MAX_ENTRIES = 32


class MarketDataProvider:
    """Provides real-time and historical market data"""

    def __init__(self):
        self.cache = {}
        self.cache_timeout = 60  # seconds a live quote counts as fresh
        self.cache_max_age = 3600  # 1 hour max for fallback when a fetch fails

        # Historical data cache: (symbol, period, interval) -> (fetched_at, DataFrame)
        self._historical_cache: dict[tuple[str, str, str], tuple[float, pd.DataFrame]] = {}

        # Rate limiting to avoid yfinance "Too Many Requests" errors.
        # Callbacks run on Dash worker threads, so the counters need a lock.
        self._rate_limit_lock = threading.Lock()
        self._last_request_time = {}
        self._min_request_interval = 0.1  # 100ms between requests per ticker
        self._global_last_request = time.time()
        self._global_min_interval = 0.05  # 50ms between any requests

        # Suppress yfinance logging
        yf_logging.getLogger('yfinance').setLevel(yf_logging.CRITICAL)

        # Common stock symbols for quick search
        self.common_symbols = {
            # Tech
            'AAPL': 'Apple Inc.', 'MSFT': 'Microsoft Corporation', 'GOOGL': 'Alphabet Inc.',
            'AMZN': 'Amazon.com Inc.', 'META': 'Meta Platforms Inc.', 'NVDA': 'NVIDIA Corporation',
            'TSLA': 'Tesla Inc.', 'NFLX': 'Netflix Inc.', 'AMD': 'Advanced Micro Devices',
            'INTC': 'Intel Corporation', 'ORCL': 'Oracle Corporation', 'CRM': 'Salesforce Inc.',
            # Finance
            'JPM': 'JPMorgan Chase', 'BAC': 'Bank of America', 'WFC': 'Wells Fargo',
            'GS': 'Goldman Sachs', 'MS': 'Morgan Stanley', 'V': 'Visa Inc.', 'MA': 'Mastercard',
            # Healthcare
            'JNJ': 'Johnson & Johnson', 'UNH': 'UnitedHealth Group', 'PFE': 'Pfizer Inc.',
            'ABBV': 'AbbVie Inc.', 'TMO': 'Thermo Fisher', 'ABT': 'Abbott Laboratories',
            # Consumer
            'WMT': 'Walmart Inc.', 'PG': 'Procter & Gamble', 'KO': 'Coca-Cola Company',
            'PEP': 'PepsiCo Inc.', 'COST': 'Costco Wholesale', 'HD': 'Home Depot',
            # Energy
            'XOM': 'Exxon Mobil', 'CVX': 'Chevron Corporation', 'COP': 'ConocoPhillips',
            # Industrial
            'BA': 'Boeing Company', 'CAT': 'Caterpillar Inc.', 'GE': 'General Electric',
            # Indices
            '^GSPC': 'S&P 500', '^DJI': 'Dow Jones', '^IXIC': 'NASDAQ', '^RUT': 'Russell 2000'
        }

    def _rate_limit(self, symbol: str = None):
        """Apply rate limiting to avoid yfinance throttling

        Args:
            symbol: Optional ticker symbol for per-ticker rate limiting
        """
        with self._rate_limit_lock:
            # Global rate limit (all requests)
            wait = self._global_min_interval - (time.time() - self._global_last_request)
            if wait > 0:
                time.sleep(wait)
            self._global_last_request = time.time()

            # Per-ticker rate limit (if symbol provided).
            # Re-read the clock here: the global sleep above already consumed
            # part of the per-ticker interval.
            if symbol:
                last_seen = self._last_request_time.get(symbol)
                if last_seen is not None:
                    wait = self._min_request_interval - (time.time() - last_seen)
                    if wait > 0:
                        time.sleep(wait)
                self._last_request_time[symbol] = time.time()

    def _get_cached_data(self, symbol: str, max_age: float | None = None) -> dict | None:
        """
        Get cached quote if available and not older than ``max_age``.

        Args:
            symbol: Stock ticker
            max_age: Maximum acceptable age in seconds. Defaults to
                ``cache_max_age``, the stale-fallback window used when a live
                fetch fails.

        Returns:
            Cached data dict or None
        """
        cached_data = self.cache.get(symbol)
        if not cached_data:
            return None

        cached_at = cached_data.get('timestamp')
        if cached_at is None:
            return None

        # total_seconds(), not .seconds: timedelta.seconds drops whole days,
        # so a 25-hour-old quote would otherwise report an age of 1 hour.
        age = (datetime.now() - cached_at).total_seconds()
        limit = self.cache_max_age if max_age is None else max_age
        if age < limit:
            logger.debug(f"Returning cached data for {symbol} (age: {age:.0f}s)")
            return cached_data
        return None

    @staticmethod
    def _coerce_price(value) -> float:
        """yfinance returns None for fields it has no value for; treat those as 0."""
        try:
            return float(value) if value is not None else 0.0
        except (TypeError, ValueError):
            return 0.0

    def get_live_price(self, symbol: str) -> dict | None:
        """
        Get current live price for a symbol
        
        Args:
            symbol: Stock ticker (e.g., 'AAPL', 'MSFT')
            
        Returns:
            Dict with price data or None
        """
        # Skip obviously invalid tickers
        if not symbol or len(symbol) > 10 or symbol.startswith('$'):
            return None

        # Serve from cache only while the quote is still fresh. Older entries
        # stay around as a fallback for when the fetch below fails.
        cached = self._get_cached_data(symbol, max_age=self.cache_timeout)
        if cached:
            return cached

        # Apply rate limiting before making API call
        self._rate_limit(symbol)

        try:
            ticker = yf.Ticker(symbol)
            info = ticker.info

            # Check if info is valid (not empty dict or None)
            if not info or not isinstance(info, dict):
                return self._get_cached_data(symbol)

            # A present-but-None field defeats dict.get()'s default, so every
            # numeric field goes through _coerce_price. Callers compare these
            # against thresholds and would raise on None.
            data = {
                'symbol': symbol,
                'price': self._coerce_price(
                    info.get('currentPrice') if info.get('currentPrice') is not None
                    else info.get('regularMarketPrice')
                ),
                'change': self._coerce_price(info.get('regularMarketChange')),
                'change_percent': self._coerce_price(info.get('regularMarketChangePercent')),
                'volume': self._coerce_price(info.get('volume')),
                'market_cap': self._coerce_price(info.get('marketCap')),
                'high': self._coerce_price(info.get('dayHigh')),
                'low': self._coerce_price(info.get('dayLow')),
                'open': self._coerce_price(info.get('open')),
                'previous_close': self._coerce_price(info.get('previousClose')),
                'name': info.get('longName') or symbol,
                'timestamp': datetime.now()
            }
            # Cache successful data
            self.cache[symbol] = data
            return data
        except Exception as e:
            # Check for rate limiting error
            if "Too Many Requests" in str(e) or "Rate limit" in str(e):
                logger.warning(f"⚠️ Rate limited on {symbol}, using cached/saved data if available")
                return self._get_cached_data(symbol)
            # Only log if it's not a simple "not found" error
            if "404" not in str(e) and "Not Found" not in str(e):
                logger.debug(f"Error fetching price for {symbol}: {e}")
            return self._get_cached_data(symbol)

    def _get_cached_history(self, key: tuple[str, str, str]) -> pd.DataFrame | None:
        """Return a private copy of a cached history frame, or None if expired."""
        entry = self._historical_cache.get(key)
        if not entry:
            return None
        fetched_at, df = entry
        if time.time() - fetched_at >= HISTORICAL_CACHE_TTL:
            self._historical_cache.pop(key, None)
            return None
        # Hand out a copy: callers localize the index or add columns in place,
        # and mutating the cached frame would corrupt every later reader.
        return df.copy()

    def _store_history(self, key: tuple[str, str, str], df: pd.DataFrame) -> None:
        """Cache a history frame, evicting the oldest entry when full."""
        if len(self._historical_cache) >= HISTORICAL_CACHE_MAX_ENTRIES:
            oldest = min(self._historical_cache, key=lambda k: self._historical_cache[k][0])
            self._historical_cache.pop(oldest, None)
        self._historical_cache[key] = (time.time(), df.copy())

    def get_historical_data(
        self,
        symbol: str,
        period: str = "1mo",
        interval: str = "1d"
    ) -> pd.DataFrame | None:
        """
        Get historical OHLCV data

        Args:
            symbol: Stock ticker
            period: Data period (1d, 5d, 1mo, 3mo, 6mo, 1y, 2y, 5y, 10y, ytd, max)
            interval: Data interval (1m, 2m, 5m, 15m, 30m, 60m, 90m, 1h, 1d, 5d, 1wk, 1mo, 3mo)

        Returns:
            DataFrame with OHLCV data
        """
        # Skip obviously invalid tickers
        if not symbol or len(symbol) > 10 or symbol.startswith('$'):
            return None

        key = (symbol, period, interval)
        cached = self._get_cached_history(key)
        if cached is not None:
            return cached

        # Apply rate limiting before making API call
        self._rate_limit(symbol)

        try:
            ticker = yf.Ticker(symbol)
            df = ticker.history(period=period, interval=interval)

            # Check if DataFrame is valid and not empty
            if df is None or df.empty:
                return None

            self._store_history(key, df)
            return df
        except Exception as e:
            # Check for rate limiting error
            if "Too Many Requests" in str(e) or "Rate limit" in str(e):
                logger.warning(f"⚠️ Rate limited on {symbol}, will use cached/saved data")
                return None
            # Only log if it's not a simple "not found" error
            if "404" not in str(e) and "Not Found" not in str(e) and "delisted" not in str(e):
                logger.debug(f"Error fetching historical data for {symbol}: {e}")
            return None

    def get_intraday_data(self, symbol: str, days: int = 1) -> pd.DataFrame | None:
        """
        Get intraday data with 1-minute intervals

        Args:
            symbol: Stock ticker
            days: Number of days (max 7 for 1m interval)

        Returns:
            DataFrame with intraday data
        """
        key = (symbol, f"{days}d", "1m")
        cached = self._get_cached_history(key)
        if cached is not None:
            return cached

        self._rate_limit(symbol)

        try:
            ticker = yf.Ticker(symbol)
            df = ticker.history(period=f"{days}d", interval="1m")
            if df is None or df.empty:
                return None
            self._store_history(key, df)
            return df
        except Exception as e:
            logger.error(f"Error fetching intraday data for {symbol}: {e}")
            return None

    def search_symbols(self, query: str, limit: int = 10) -> list[dict]:
        """
        Search for stock symbols matching query

        Args:
            query: Search string (symbol or company name)
            limit: Maximum number of results

        Returns:
            List of matching symbols with metadata
        """
        if not query or len(query) < 1:
            return []

        query_upper = query.upper().strip()
        query_lower = query.lower()
        results = []

        # Search in common symbols
        for symbol, name in self.common_symbols.items():
            if query_upper in symbol or query_lower in name.lower():
                results.append({
                    'symbol': symbol,
                    'name': name,
                    'type': 'INDEX' if symbol.startswith('^') else 'EQUITY'
                })

                if len(results) >= limit:
                    break

        # If no results, try yfinance ticker validation
        if not results and len(query) >= 1:
            try:
                ticker = yf.Ticker(query_upper)
                info = ticker.info
                if info and info.get('symbol'):
                    results.append({
                        'symbol': info.get('symbol', query_upper),
                        'name': info.get('longName', 'Unknown'),
                        'type': info.get('quoteType', 'EQUITY')
                    })
            except Exception as e:
                logger.debug(f"Symbol lookup failed for {query}: {e}")

        return results

    def get_multiple_quotes(self, symbols: list[str]) -> dict[str, dict]:
        """
        Get quotes for multiple symbols at once
        
        Args:
            symbols: List of stock tickers
            
        Returns:
            Dict mapping symbol to quote data
        """
        quotes = {}
        for symbol in symbols:
            quote = self.get_live_price(symbol)
            if quote:
                quotes[symbol] = quote
        return quotes

    def get_market_indices(self) -> dict[str, dict]:
        """
        Get major market indices
        
        Returns:
            Dict with index data
        """
        indices = {
            'S&P 500': '^GSPC',
            'Dow Jones': '^DJI',
            'NASDAQ': '^IXIC',
            'Russell 2000': '^RUT',
            'VIX': '^VIX'
        }

        index_data = {}
        for name, symbol in indices.items():
            data = self.get_live_price(symbol)
            if data:
                index_data[name] = data

        return index_data


# Shared instance. Import this rather than constructing MarketDataProvider():
# separate instances keep separate rate-limit counters and caches, which is
# what triggers yfinance's "Too Many Requests" in the first place.
market_data = MarketDataProvider()
