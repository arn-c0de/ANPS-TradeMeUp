"""
Charts Tab - Data Retrieval Functions
"""

from typing import Dict, Optional

import pandas as pd

from src.gui.tabs.charts.chart_data_manager import get_chart_data_manager
from src.services.market_data import market_data

# Initialize market data provider


def _fetch_chart_data(symbol: str, timeframe: str, loaded_data: pd.DataFrame | None = None) -> pd.DataFrame | None:
    """
    Fetch chart data, using loaded_data if provided (for infinite scroll).
    
    Args:
        symbol: Stock ticker symbol
        timeframe: Chart timeframe
        loaded_data: Optional pre-loaded DataFrame
        
    Returns:
        DataFrame with OHLCV data or None if error
    """
    if loaded_data is not None and not loaded_data.empty:
        return loaded_data

    # Use ChartDataManager for initial load
    data_manager = get_chart_data_manager()
    df = data_manager.get_initial_data(symbol, timeframe)

    if df is None or df.empty:
        # Fallback to direct market_data call
        if timeframe == '1d_1m':
            df = market_data.get_intraday_data(symbol, days=1)
        elif timeframe == '5d_5m':
            df = market_data.get_historical_data(symbol, period='5d', interval='5m')
        else:
            df = market_data.get_historical_data(symbol, period=timeframe)

    return df


def _calculate_stats(df: pd.DataFrame, symbol: str) -> dict | None:
    """
    Calculate statistics from DataFrame.
    
    Args:
        df: DataFrame with OHLCV data
        symbol: Stock ticker symbol
        
    Returns:
        Dictionary with stats or None if error
    """
    if df is None or df.empty:
        return None

    try:
        current_price = df['Close'].iloc[-1]
        first_price = df['Close'].iloc[0]
        price_change = current_price - first_price
        price_change_pct = (price_change / first_price) * 100
        high = df['High'].max()
        low = df['Low'].min()
        volume = df['Volume'].iloc[-1] if 'Volume' in df.columns else 0

        color = "success" if price_change >= 0 else "danger"
        arrow = "🔼" if price_change >= 0 else "🔽"

        return {
            'symbol': symbol,
            'current_price': current_price,
            'price_change': price_change,
            'price_change_pct': price_change_pct,
            'high': high,
            'low': low,
            'volume': volume,
            'color': color,
            'arrow': arrow
        }
    except Exception as e:
        return None
