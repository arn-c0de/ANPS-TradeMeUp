"""
Charts Tab Package
Entry point for charts tab module
"""

from .layout import create_layout
from .callbacks import register_charts_callbacks, register_callbacks

# Export functions for backward compatibility and callbacks
from .components import (
    render_multi_panel_layout,
    get_stock_chart_components,
    create_trading_overlay,
    create_chart_panel,
    get_stock_chart_with_stats,
    get_comparison_chart,
    get_market_indices_cards,
    get_price_indicator
)

__all__ = [
    'create_layout',
    'register_charts_callbacks',
    'register_callbacks',
    'render_multi_panel_layout',
    'get_stock_chart_components',
    'create_trading_overlay',
    'create_chart_panel',
    'get_stock_chart_with_stats',
    'get_comparison_chart',
    'get_market_indices_cards',
    'get_price_indicator'
]
