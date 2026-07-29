"""
Chart Data Manager
Manages chart data loading, caching, and infinite scroll functionality
Follows patterns from MarketDataProvider for consistency
"""

import hashlib
import logging
import threading
from datetime import datetime, timedelta, timezone
from functools import lru_cache
from typing import Dict, Optional, Tuple

import pandas as pd

from src.services.market_data import market_data

logger = logging.getLogger(__name__)

# Constants (avoid magic numbers)
THRESHOLD_PERCENTAGE = 0.1  # 10% of data visible on left side triggers load
MAX_LOADED_CHARTS = 10  # Memory limit for loaded charts
DEBOUNCE_MS_SERVER = 100  # Server-side debouncing in milliseconds

# Load amounts per timeframe (how much additional data to fetch)
LOAD_AMOUNTS = {
    '1d_1m': timedelta(days=1),
    '5d_5m': timedelta(days=2),
    '1mo': timedelta(days=30),
    '3mo': timedelta(days=60),
    '6mo': timedelta(days=90),
    '1y': timedelta(days=180),
    '2y': timedelta(days=365),
    '5y': timedelta(days=730),
}


class ChartDataManager:
    """
    Manages chart data loading and caching for infinite scroll functionality.
    
    Thread-safe implementation with LRU cache for performance.
    Follows patterns from MarketDataProvider for consistency.
    """

    def __init__(self):
        """Initialize ChartDataManager with market data provider."""
        # Shared provider: a private instance would bypass the global rate limit.
        self.market_data = market_data
        self._cache: dict[str, pd.DataFrame] = {}
        self._cache_metadata: dict[str, dict] = {}
        self._lock = threading.Lock()
        self._access_order: list = []  # For LRU eviction

    def _get_cache_key(self, symbol: str, timeframe: str, start_date: datetime | None = None, end_date: datetime | None = None) -> str:
        """Generate cache key for chart data."""
        key_parts = [symbol, timeframe]
        if start_date:
            key_parts.append(start_date.isoformat())
        if end_date:
            key_parts.append(end_date.isoformat())
        return ':'.join(key_parts)

    def _update_access_order(self, cache_key: str):
        """Update LRU access order."""
        if cache_key in self._access_order:
            self._access_order.remove(cache_key)
        self._access_order.append(cache_key)

        # Evict oldest if over limit
        if len(self._access_order) > MAX_LOADED_CHARTS:
            oldest_key = self._access_order.pop(0)
            if oldest_key in self._cache:
                del self._cache[oldest_key]
            if oldest_key in self._cache_metadata:
                del self._cache_metadata[oldest_key]
            logger.debug(f"Evicted chart data from cache: {oldest_key}")

    def get_initial_data(self, symbol: str, timeframe: str) -> pd.DataFrame | None:
        """
        Load initial chart data based on timeframe.
        
        Args:
            symbol: Stock ticker symbol
            timeframe: Chart timeframe (e.g., '1mo', '1y')
            
        Returns:
            DataFrame with OHLCV data or None if error
        """
        try:
            # Use existing MarketDataProvider methods
            if timeframe == '1d_1m':
                df = self.market_data.get_intraday_data(symbol, days=1)
            elif timeframe == '5d_5m':
                df = self.market_data.get_historical_data(symbol, period='5d', interval='5m')
            else:
                df = self.market_data.get_historical_data(symbol, period=timeframe)

            if df is None or df.empty:
                return None

            # Cache the data
            cache_key = self._get_cache_key(symbol, timeframe)
            with self._lock:
                self._cache[cache_key] = df.copy()
                self._cache_metadata[cache_key] = {
                    'symbol': symbol,
                    'timeframe': timeframe,
                    'earliest_date': df.index[0] if len(df) > 0 else None,
                    'latest_date': df.index[-1] if len(df) > 0 else None,
                    'data_points': len(df),
                    'loaded_at': datetime.now()
                }
                self._update_access_order(cache_key)

            logger.debug(f"Loaded initial data for {symbol} ({timeframe}): {len(df)} points")
            return df

        except Exception as e:
            logger.error(f"Error loading initial data for {symbol} ({timeframe}): {e}")
            return None

    def load_more_future(self, symbol: str, timeframe: str, current_latest_date: datetime) -> pd.DataFrame | None:
        """
        Load additional future data after current_latest_date.
        
        Args:
            symbol: Stock ticker symbol
            timeframe: Chart timeframe
            current_latest_date: Current latest date in loaded data
            
        Returns:
            DataFrame with additional future data or None if error/no more data
        """
        try:
            # Determine how much data to load
            load_amount = LOAD_AMOUNTS.get(timeframe, timedelta(days=30))

            # Ensure current_latest_date is timezone-aware (yfinance data is UTC)
            if current_latest_date.tzinfo is None:
                current_latest_date = pd.Timestamp(current_latest_date, tz='UTC')

            target_end_date = current_latest_date + load_amount

            # Get current time as timezone-aware
            now_utc = pd.Timestamp.now(tz='UTC')

            # Calculate period string for yfinance (from now to target_end_date)
            days_diff = (target_end_date - now_utc).days

            # For future data, we typically want recent data up to now
            # Calculate period from current_latest_date to now
            days_from_latest = (now_utc - current_latest_date).days

            if days_from_latest <= 7:
                period = '7d'
            elif days_from_latest <= 30:
                period = '1mo'
            elif days_from_latest <= 90:
                period = '3mo'
            elif days_from_latest <= 180:
                period = '6mo'
            elif days_from_latest <= 365:
                period = '1y'
            elif days_from_latest <= 730:
                period = '2y'
            else:
                period = '5y'

            # Determine interval based on timeframe
            interval = '1d'
            if timeframe == '1d_1m':
                interval = '1m'
            elif timeframe == '5d_5m':
                interval = '5m'

            # Fetch data
            df = self.market_data.get_historical_data(symbol, period=period, interval=interval)

            if df is None or df.empty:
                logger.debug(f"No more future data available for {symbol}")
                return None

            # Filter to only data after current_latest_date
            # Ensure timezone compatibility for comparison
            if not df.empty and df.index.tzinfo is not None and current_latest_date.tzinfo is None:
                current_latest_date = pd.Timestamp(current_latest_date, tz=df.index.tzinfo)
            elif not df.empty and df.index.tzinfo is None and current_latest_date.tzinfo is not None:
                current_latest_date = current_latest_date.tz_localize(None)

            df = df[df.index > current_latest_date]

            if df.empty:
                logger.debug(f"No additional data after {current_latest_date} for {symbol}")
                return None

            logger.debug(f"Loaded {len(df)} additional future data points for {symbol}")
            return df

        except Exception as e:
            logger.error(f"Error loading more future data for {symbol}: {e}")
            return None

    def load_more_historical(self, symbol: str, timeframe: str, current_earliest_date: datetime) -> pd.DataFrame | None:
        """
        Load additional historical data before current_earliest_date.
        
        Args:
            symbol: Stock ticker symbol
            timeframe: Chart timeframe
            current_earliest_date: Current earliest date in loaded data
            
        Returns:
            DataFrame with additional historical data or None if error/no more data
        """
        try:
            # Determine how much data to load
            load_amount = LOAD_AMOUNTS.get(timeframe, timedelta(days=30))

            # Ensure current_earliest_date is timezone-aware (yfinance data is UTC)
            if current_earliest_date.tzinfo is None:
                current_earliest_date = pd.Timestamp(current_earliest_date, tz='UTC')

            target_start_date = current_earliest_date - load_amount

            # Get current time as timezone-aware
            now_utc = pd.Timestamp.now(tz='UTC')

            # Calculate period string for yfinance
            days_diff = (now_utc - target_start_date).days

            if days_diff <= 7:
                period = '7d'
            elif days_diff <= 30:
                period = '1mo'
            elif days_diff <= 90:
                period = '3mo'
            elif days_diff <= 180:
                period = '6mo'
            elif days_diff <= 365:
                period = '1y'
            elif days_diff <= 730:
                period = '2y'
            else:
                period = '5y'

            # Determine interval based on timeframe
            interval = '1d'
            if timeframe == '1d_1m':
                interval = '1m'
            elif timeframe == '5d_5m':
                interval = '5m'

            # Fetch data
            df = self.market_data.get_historical_data(symbol, period=period, interval=interval)

            if df is None or df.empty:
                logger.debug(f"No more historical data available for {symbol}")
                return None

            # Filter to only data before current_earliest_date
            # Ensure timezone compatibility for comparison
            if not df.empty and df.index.tzinfo is not None and current_earliest_date.tzinfo is None:
                current_earliest_date = pd.Timestamp(current_earliest_date, tz=df.index.tzinfo)
            elif not df.empty and df.index.tzinfo is None and current_earliest_date.tzinfo is not None:
                current_earliest_date = current_earliest_date.tz_localize(None)

            df = df[df.index < current_earliest_date]

            if df.empty:
                logger.debug(f"No additional data before {current_earliest_date} for {symbol}")
                return None

            logger.debug(f"Loaded {len(df)} additional historical data points for {symbol}")
            return df

        except Exception as e:
            logger.error(f"Error loading more historical data for {symbol}: {e}")
            return None

    def prepend_data(self, existing_df: pd.DataFrame, new_df: pd.DataFrame) -> pd.DataFrame:
        """
        Prepend new data to existing DataFrame efficiently.
        
        Args:
            existing_df: Existing DataFrame
            new_df: New DataFrame to prepend
            
        Returns:
            Combined DataFrame with new data at the beginning
        """
        if new_df is None or new_df.empty:
            return existing_df

        if existing_df is None or existing_df.empty:
            return new_df

        # Use pd.concat for efficient prepending
        combined = pd.concat([new_df, existing_df])

        # Remove duplicates (keep last occurrence)
        combined = combined[~combined.index.duplicated(keep='last')]

        # Sort by index to ensure chronological order
        combined = combined.sort_index()

        return combined

    def append_data(self, existing_df: pd.DataFrame, new_df: pd.DataFrame) -> pd.DataFrame:
        """
        Append new data to existing DataFrame efficiently.
        
        Args:
            existing_df: Existing DataFrame
            new_df: New DataFrame to append
            
        Returns:
            Combined DataFrame with new data at the end
        """
        if new_df is None or new_df.empty:
            return existing_df

        if existing_df is None or existing_df.empty:
            return new_df

        # Use pd.concat for efficient appending
        combined = pd.concat([existing_df, new_df])

        # Remove duplicates (keep last occurrence)
        combined = combined[~combined.index.duplicated(keep='last')]

        # Sort by index to ensure chronological order
        combined = combined.sort_index()

        return combined

    def should_load_more_left(self, visible_left_index: int, total_data_points: int, buffer_size: int = 0) -> bool:
        """
        Determine if more historical data should be loaded based on threshold and buffer zone.
        
        Args:
            visible_left_index: Index of leftmost visible data point
            total_data_points: Total number of loaded data points
            buffer_size: Buffer zone size (number of candles to maintain before visible area)
            
        Returns:
            True if more data should be loaded, False otherwise
        """
        if total_data_points == 0:
            return False

        # Use buffer zone if provided, otherwise use percentage threshold
        if buffer_size > 0:
            return visible_left_index < buffer_size
        else:
            # Fallback to percentage threshold
            percentage_before = visible_left_index / total_data_points
            return percentage_before < THRESHOLD_PERCENTAGE

    def should_load_more_right(self, visible_right_index: int, total_data_points: int, buffer_size: int = 0) -> bool:
        """
        Determine if more future data should be loaded based on threshold and buffer zone.
        
        Args:
            visible_right_index: Index of rightmost visible data point
            total_data_points: Total number of loaded data points
            buffer_size: Buffer zone size (number of candles to maintain after visible area)
            
        Returns:
            True if more data should be loaded, False otherwise
        """
        if total_data_points == 0:
            return False

        # Use buffer zone if provided, otherwise use percentage threshold
        if buffer_size > 0:
            return visible_right_index > (total_data_points - buffer_size)
        else:
            # Fallback to percentage threshold
            percentage_after = (total_data_points - visible_right_index) / total_data_points
            return percentage_after < THRESHOLD_PERCENTAGE

    def should_load_more(self, visible_left_index: int, total_data_points: int) -> bool:
        """
        Determine if more data should be loaded based on threshold (legacy method for backward compatibility).
        
        Args:
            visible_left_index: Index of leftmost visible data point
            total_data_points: Total number of loaded data points
            
        Returns:
            True if more data should be loaded, False otherwise
        """
        return self.should_load_more_left(visible_left_index, total_data_points)

    def get_load_amount(self, timeframe: str) -> timedelta:
        """
        Get the load amount for a given timeframe.
        
        Args:
            timeframe: Chart timeframe
            
        Returns:
            timedelta representing how much data to load
        """
        return LOAD_AMOUNTS.get(timeframe, timedelta(days=30))

    def get_cached_data(self, symbol: str, timeframe: str) -> pd.DataFrame | None:
        """
        Get cached data if available.
        
        Args:
            symbol: Stock ticker symbol
            timeframe: Chart timeframe
            
        Returns:
            Cached DataFrame or None
        """
        cache_key = self._get_cache_key(symbol, timeframe)
        with self._lock:
            if cache_key in self._cache:
                self._update_access_order(cache_key)
                return self._cache[cache_key].copy()
        return None

    def update_cached_data(self, symbol: str, timeframe: str, df: pd.DataFrame):
        """
        Update cached data with new DataFrame.
        
        Args:
            symbol: Stock ticker symbol
            timeframe: Chart timeframe
            df: New DataFrame to cache
        """
        cache_key = self._get_cache_key(symbol, timeframe)
        with self._lock:
            self._cache[cache_key] = df.copy()
            self._cache_metadata[cache_key] = {
                'symbol': symbol,
                'timeframe': timeframe,
                'earliest_date': df.index[0] if len(df) > 0 else None,
                'latest_date': df.index[-1] if len(df) > 0 else None,
                'data_points': len(df),
                'loaded_at': datetime.now()
            }
            self._update_access_order(cache_key)

    def get_cache_metadata(self, symbol: str, timeframe: str) -> dict | None:
        """
        Get metadata for cached data.
        
        Args:
            symbol: Stock ticker symbol
            timeframe: Chart timeframe
            
        Returns:
            Metadata dict or None
        """
        cache_key = self._get_cache_key(symbol, timeframe)
        with self._lock:
            return self._cache_metadata.get(cache_key, {}).copy() if cache_key in self._cache_metadata else None


# Global instance (singleton pattern)
_chart_data_manager: ChartDataManager | None = None

def get_chart_data_manager() -> ChartDataManager:
    """Get global ChartDataManager instance."""
    global _chart_data_manager
    if _chart_data_manager is None:
        _chart_data_manager = ChartDataManager()
    return _chart_data_manager
