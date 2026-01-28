"""
Live Market Data Provider
Fetches real-time stock market data from various sources
"""
import warnings
import os
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

import yfinance as yf
import pandas as pd
from datetime import datetime, timedelta
from typing import Dict, List, Optional
import logging
import time
from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception_type
from functools import lru_cache

logger = logging.getLogger(__name__)


# Retry decorator for network failures
def retry_on_network_error(func):
    """Decorator to retry on network-related errors"""
    return retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=2, max=10),
        retry=retry_if_exception_type((ConnectionError, TimeoutError)),
        reraise=True
    )(func)


class MarketDataProvider:
    """Provides real-time and historical market data"""

    def __init__(self):
        self.cache = {}
        self.cache_timeout = 60  # seconds
        self.cache_max_age = 3600  # 1 hour max for fallback
        
        # Rate limiting to avoid yfinance "Too Many Requests" errors
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
        current_time = time.time()
        
        # Global rate limit (all requests)
        time_since_last_global = current_time - self._global_last_request
        if time_since_last_global < self._global_min_interval:
            time.sleep(self._global_min_interval - time_since_last_global)
        self._global_last_request = time.time()
        
        # Per-ticker rate limit (if symbol provided)
        if symbol:
            if symbol in self._last_request_time:
                time_since_last = current_time - self._last_request_time[symbol]
                if time_since_last < self._min_request_interval:
                    time.sleep(self._min_request_interval - time_since_last)
            self._last_request_time[symbol] = time.time()
    
    def _get_cached_data(self, symbol: str) -> Optional[Dict]:
        """
        Get cached data if available and not too old
        
        Args:
            symbol: Stock ticker
            
        Returns:
            Cached data dict or None
        """
        if symbol in self.cache:
            cached_data = self.cache[symbol]
            age = (datetime.now() - cached_data.get('timestamp', datetime.min)).seconds
            if age < self.cache_max_age:
                logger.info(f"Returning cached data for {symbol} (age: {age}s)")
                return cached_data
        return None
    
    def get_live_price(self, symbol: str) -> Optional[Dict]:
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
        
        # Check cache first to avoid unnecessary API calls
        cached = self._get_cached_data(symbol)
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
            
            data = {
                'symbol': symbol,
                'price': info.get('currentPrice', info.get('regularMarketPrice', 0)),
                'change': info.get('regularMarketChange', 0),
                'change_percent': info.get('regularMarketChangePercent', 0),
                'volume': info.get('volume', 0),
                'market_cap': info.get('marketCap', 0),
                'high': info.get('dayHigh', 0),
                'low': info.get('dayLow', 0),
                'open': info.get('open', 0),
                'previous_close': info.get('previousClose', 0),
                'name': info.get('longName', symbol),
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
    
    @lru_cache(maxsize=32)
    def get_historical_data(
        self, 
        symbol: str, 
        period: str = "1mo",
        interval: str = "1d"
    ) -> Optional[pd.DataFrame]:
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
        
        # Apply rate limiting before making API call
        self._rate_limit(symbol)
            
        try:
            ticker = yf.Ticker(symbol)
            df = ticker.history(period=period, interval=interval)
            
            # Check if DataFrame is valid and not empty
            if df is None or df.empty:
                return None
                
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
    
    @lru_cache(maxsize=32)
    def get_intraday_data(self, symbol: str, days: int = 1) -> Optional[pd.DataFrame]:
        """
        Get intraday data with 1-minute intervals

        Args:
            symbol: Stock ticker
            days: Number of days (max 7 for 1m interval)

        Returns:
            DataFrame with intraday data
        """
        try:
            ticker = yf.Ticker(symbol)
            df = ticker.history(period=f"{days}d", interval="1m")
            return df
        except Exception as e:
            logger.error(f"Error fetching intraday data for {symbol}: {e}")
            return None

    def search_symbols(self, query: str, limit: int = 10) -> List[Dict]:
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

    def get_multiple_quotes(self, symbols: List[str]) -> Dict[str, Dict]:
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
    
    def get_market_indices(self) -> Dict[str, Dict]:
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
    
    def search_symbol(self, query: str) -> List[Dict]:
        """
        Search for stock symbols
        
        Args:
            query: Search query
            
        Returns:
            List of matching symbols with info
        """
        try:
            # This is a simple implementation
            # For production, use a proper symbol search API
            ticker = yf.Ticker(query.upper())
            info = ticker.info
            
            return [{
                'symbol': query.upper(),
                'name': info.get('longName', query),
                'exchange': info.get('exchange', 'Unknown'),
                'type': info.get('quoteType', 'EQUITY')
            }]
        except Exception as e:
            logger.error(f"Error searching symbol {query}: {e}")
            return []


# Global instance
market_data = MarketDataProvider()
