"""
Backward compatibility redirect for MarketDataProvider
Moved to src.services.market_data to avoid circular dependencies
"""
# Import from new location
from src.services.market_data import MarketDataProvider, market_data

__all__ = ['MarketDataProvider', 'market_data']
