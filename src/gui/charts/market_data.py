"""
Live Market Data Provider
Fetches real-time stock market data from various sources
"""
import warnings
warnings.filterwarnings('ignore', category=FutureWarning, module='yfinance')
import yfinance as yf
import pandas as pd
from datetime import datetime, timedelta
from typing import Dict, List, Optional
import logging

logger = logging.getLogger(__name__)


class MarketDataProvider:
    """Provides real-time and historical market data"""
    
    def __init__(self):
        self.cache = {}
        self.cache_timeout = 60  # seconds
    
    def get_live_price(self, symbol: str) -> Optional[Dict]:
        """
        Get current live price for a symbol
        
        Args:
            symbol: Stock ticker (e.g., 'AAPL', 'MSFT')
            
        Returns:
            Dict with price data or None
        """
        try:
            ticker = yf.Ticker(symbol)
            info = ticker.info
            
            return {
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
        except Exception as e:
            logger.error(f"Error fetching price for {symbol}: {e}")
            return None
    
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
        try:
            ticker = yf.Ticker(symbol)
            df = ticker.history(period=period, interval=interval)
            return df
        except Exception as e:
            logger.error(f"Error fetching historical data for {symbol}: {e}")
            return None
    
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
